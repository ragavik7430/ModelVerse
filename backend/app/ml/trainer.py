import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any

import joblib
import mlflow
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from app.config.settings import settings
from app.ml.algorithms import create_estimator
from app.ml.evaluator import COMPARISON_POLICIES, evaluate_clustering, evaluate_supervised, select_best_model
from app.ml.experiment_tracker import get_or_create_experiment
from app.ml.optimizer import optimize_parameters
from app.ml.preprocessing import build_training_pipeline
from app.ml.registry import store_model
from app.models.experiment import Experiment, TrainedModel


logger = logging.getLogger(__name__)


def _json_value(value: Any):
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def validate_training_frame(frame: pd.DataFrame, experiment: Experiment, allow_identifier_target: bool = False) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("The selected dataset has no training rows.")
    if not frame.columns.is_unique:
        raise ValueError("Dataset column names must be unique before training.")

    prepared = frame.copy(deep=True)
    prepared.columns = [str(column).strip() for column in prepared.columns]
    if not pd.Index(prepared.columns).is_unique:
        raise ValueError("Dataset column names must be unique before training.")

    if experiment.problem_type == "clustering":
        if experiment.target_column:
            raise ValueError("Clustering experiments do not use a target column.")
        if len(prepared) < 6:
            raise ValueError("At least six rows are required for reproducible train, validation, and test splits.")
        return prepared.replace([np.inf, -np.inf], np.nan)

    target_column = experiment.target_column
    if not target_column or target_column not in prepared.columns:
        raise ValueError("The selected target column is not present in this dataset.")

    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", target_column)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_").lower()
    identifier_tokens = {"id", "uuid", "index", "identifier", "key"}
    is_identifier = (
        normalized in identifier_tokens
        or normalized.startswith("id_")
        or normalized.endswith("_id")
        or normalized.endswith("_uuid")
        or normalized.endswith("_index")
        or normalized.endswith("_identifier")
    )
    if is_identifier and not allow_identifier_target:
        raise ValueError("The selected target appears to be an identifier. Explicitly allow it only if predicting an identifier is intentional.")

    target = prepared[target_column]
    non_missing = target.notna()
    if not non_missing.any():
        raise ValueError("The selected target column contains no usable values.")

    if experiment.problem_type == "regression":
        numeric_target = pd.to_numeric(target, errors="coerce")
        usable = numeric_target.notna()
        if not usable.any():
            raise ValueError("Regression requires a numeric target column.")
        prepared = prepared.loc[usable].copy()
        prepared[target_column] = numeric_target.loc[usable].astype(float)
        if prepared[target_column].nunique() < 2:
            raise ValueError("Regression requires at least two distinct target values.")
    elif experiment.problem_type == "classification":
        prepared = prepared.loc[non_missing].copy()
        if prepared[target_column].nunique() < 2:
            raise ValueError("Classification requires at least two target classes.")
        if (
            pd.api.types.is_numeric_dtype(prepared[target_column])
            and prepared[target_column].nunique() >= max(20, len(prepared) / 2)
        ):
            raise ValueError("Classification requires a discrete class target, not a likely continuous numeric target.")
    else:
        raise ValueError("The selected problem type is not supported.")

    if len(prepared) < 6:
        raise ValueError("At least six rows with usable target values are required for reproducible train, validation, and test splits.")
    if len(prepared.columns) < 2:
        raise ValueError("At least one feature column in addition to the target is required.")
    return prepared.replace([np.inf, -np.inf], np.nan)


def _stratification_target(target, split_size: float, random_state: int):
    counts = target.value_counts(dropna=False)
    class_count = len(counts)
    remaining_count = len(target) - int(np.ceil(len(target) * split_size))
    if class_count < 2 or counts.min() < 2 or int(np.ceil(len(target) * split_size)) < class_count or remaining_count < class_count:
        return None
    return target


def _split_data(features: pd.DataFrame, target, experiment: Experiment):
    if target is None:
        train_validation_features, test_features = train_test_split(
            features,
            test_size=experiment.test_size,
            random_state=experiment.random_state,
        )
        train_features, validation_features = train_test_split(
            train_validation_features,
            test_size=0.2,
            random_state=experiment.random_state,
        )
        return train_features, validation_features, test_features, None, None, None

    stratify = _stratification_target(target, experiment.test_size, experiment.random_state) if target is not None and experiment.problem_type == "classification" else None
    train_validation_features, test_features, train_validation_target, test_target = train_test_split(
        features,
        target,
        test_size=experiment.test_size,
        random_state=experiment.random_state,
        stratify=stratify,
    )

    validation_fraction = 0.2
    validation_stratify = None
    if train_validation_target is not None and experiment.problem_type == "classification":
        validation_stratify = _stratification_target(
            train_validation_target,
            validation_fraction,
            experiment.random_state,
        )
    train_features, validation_features, train_target, validation_target = train_test_split(
        train_validation_features,
        train_validation_target,
        test_size=validation_fraction,
        random_state=experiment.random_state,
        stratify=validation_stratify,
    )
    return (
        train_features,
        validation_features,
        test_features,
        train_target,
        validation_target,
        test_target,
    )


def _flatten_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    flattened = {}
    for split_name, split_metrics in metrics.items():
        if not isinstance(split_metrics, dict):
            continue
        for metric_name, value in split_metrics.items():
            if isinstance(value, (int, float)) and np.isfinite(value):
                flattened[f"{split_name}.{metric_name}"] = float(value)
    return flattened


def _log_candidate(
    experiment: Experiment,
    record: TrainedModel,
    parameters: dict[str, Any],
    metrics: dict[str, Any],
    preprocessing: dict[str, Any],
    artifact_file: str,
) -> str:
    experiment_id = get_or_create_experiment(experiment.experiment_name)
    with mlflow.start_run(experiment_id=experiment_id, run_name=f"{experiment.id}-{record.algorithm}") as run:
        mlflow.set_tags(
            {
                "modelverse.experiment_id": str(experiment.id),
                "modelverse.model_id": str(record.id),
                "modelverse.dataset_id": str(experiment.dataset_id),
                "modelverse.problem_type": experiment.problem_type,
                "modelverse.target_column": experiment.target_column or "",
                "modelverse.algorithm": record.algorithm,
                "modelverse.random_state": str(experiment.random_state),
                "modelverse.training_status": "completed",
            }
        )
        mlflow.log_params({key: str(value) for key, value in parameters.items()})
        mlflow.log_metrics(_flatten_metrics(metrics))
        mlflow.log_dict(preprocessing, "preprocessing.json")
        mlflow.log_artifact(artifact_file, artifact_path="model")
        return run.info.run_id


def _trial_configuration() -> tuple[int, int]:
    n_trials = settings.OPTUNA_N_TRIALS
    timeout_seconds = settings.OPTUNA_TIMEOUT_SECONDS
    if not 1 <= n_trials <= 20:
        raise ValueError("OPTUNA_N_TRIALS must be between 1 and 20.")
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("OPTUNA_TIMEOUT_SECONDS must be between 1 and 600.")
    return n_trials, timeout_seconds


def _train_candidate(db, experiment: Experiment, record: TrainedModel, splits, optimize: bool, n_trials: int, timeout_seconds: int):
    train_features, validation_features, test_features, train_target, validation_target, test_target = splits
    parameters: dict[str, Any] = {}
    if optimize:
        parameters, best_objective = optimize_parameters(
            experiment.problem_type,
            record.algorithm,
            experiment.random_state,
            train_features,
            train_target,
            validation_features,
            validation_target,
            n_trials,
            timeout_seconds,
        )
        record.metrics = {"optimization": {"best_objective": best_objective, "n_trials": n_trials}}

    estimator = create_estimator(experiment.problem_type, record.algorithm, experiment.random_state, parameters)
    pipeline, preprocessing = build_training_pipeline(train_features, estimator)
    pipeline.fit(train_features, train_target)

    if experiment.problem_type == "clustering":
        preprocessor = pipeline.named_steps["preprocessing"]
        train_features_transformed = preprocessor.transform(train_features)
        validation_features_transformed = preprocessor.transform(validation_features)
        test_features_transformed = preprocessor.transform(test_features)
        train_labels = pipeline.named_steps["model"].predict(train_features_transformed)
        validation_labels = pipeline.named_steps["model"].predict(validation_features_transformed)
        test_labels = pipeline.named_steps["model"].predict(test_features_transformed)
        metrics = evaluate_clustering(
            train_features_transformed,
            train_labels,
            validation_features_transformed,
            validation_labels,
            test_features_transformed,
            test_labels,
        )
    else:
        metrics = evaluate_supervised(
            experiment.problem_type,
            train_target,
            pipeline.predict(train_features),
            validation_target,
            pipeline.predict(validation_features),
            test_target,
            pipeline.predict(test_features),
        )

    if optimize:
        metrics["optimization"] = {
            "best_objective": float(best_objective),
            "objective_metric": "validation.rmse" if experiment.problem_type == "regression" else "validation.f1_macro" if experiment.problem_type == "classification" else "validation.silhouette",
            "n_trials": n_trials,
            "random_state": experiment.random_state,
            "best_parameters": parameters,
        }

    record.parameters = _json_value({**pipeline.named_steps["model"].get_params(deep=False)})
    record.preprocessing = preprocessing
    record.metrics = _json_value(metrics)

    artifact_root = settings.MODEL_ARTIFACT_STORAGE_PATH
    os.makedirs(artifact_root, exist_ok=True)
    file_descriptor, temporary_artifact = tempfile.mkstemp(suffix=".joblib", dir=artifact_root)
    os.close(file_descriptor)
    try:
        joblib.dump(pipeline, temporary_artifact)
        run_id = _log_candidate(experiment, record, record.parameters, record.metrics, preprocessing, temporary_artifact)
        artifact_key = store_model(experiment.id, record.id, pipeline)
    finally:
        if os.path.exists(temporary_artifact):
            os.unlink(temporary_artifact)

    record.mlflow_run_id = run_id
    record.artifact_key = artifact_key
    record.status = "completed"
    record.error_message = None
    db.commit()
    db.refresh(record)


def run_experiment(db, experiment: Experiment, frame: pd.DataFrame, allow_identifier_target: bool = False) -> Experiment:
    n_trials, timeout_seconds = _trial_configuration() if experiment.configuration.get("optimize") else (0, 0)
    original_row_count = len(frame)
    prepared = validate_training_frame(frame, experiment, allow_identifier_target)
    excluded_target_rows = original_row_count - len(prepared)
    target_column = experiment.target_column
    if experiment.problem_type == "clustering":
        features = prepared
        target = None
    else:
        features = prepared.drop(columns=[target_column])
        target = prepared[target_column]
    if features.empty or not len(features.columns):
        raise ValueError("No usable feature columns remain for training.")

    splits = _split_data(features, target, experiment)
    experiment.configuration = {
        **experiment.configuration,
        "n_trials": n_trials if experiment.configuration.get("optimize") else None,
        "validation_fraction_of_training_data": 0.2,
        "split_policy": "deterministic random split; classification stratified when valid",
        "preprocessing_policy": "numeric median imputation and scaling; categorical constant imputation and one-hot encoding; fit on train split only",
        "target_rows_excluded": excluded_target_rows,
        "split_row_counts": {
            "train": len(splits[0]),
            "validation": len(splits[1]),
            "test": len(splits[2]),
        },
    }
    experiment.comparison_policy = COMPARISON_POLICIES[experiment.problem_type]
    db.commit()

    for algorithm in experiment.configuration["selected_algorithms"]:
        record = TrainedModel(
            experiment_id=experiment.id,
            name=algorithm,
            algorithm=algorithm,
            status="running",
            parameters={},
            metrics={},
            preprocessing={},
        )
        experiment.models.append(record)
        db.add(record)
        db.commit()
        db.refresh(record)
        try:
            _train_candidate(
                db,
                experiment,
                record,
                splits,
                bool(experiment.configuration.get("optimize")),
                n_trials,
                timeout_seconds,
            )
        except Exception as exc:
            logger.exception("Training candidate failed (experiment_id=%s, model_id=%s).", experiment.id, record.id)
            db.rollback()
            record = db.query(TrainedModel).filter(TrainedModel.id == record.id).first()
            if record is None:
                raise RuntimeError("The failed candidate could not be restored from the experiment record.")
            record.status = "failed"
            record.error_message = "Training failed for this dataset and candidate; review the data and selected configuration."
            db.commit()

    db.refresh(experiment)
    completed_models = (
        db.query(TrainedModel)
        .filter(TrainedModel.experiment_id == experiment.id, TrainedModel.status == "completed")
        .all()
    )
    best_model = select_best_model(experiment.problem_type, completed_models)
    experiment.best_model_id = best_model.id if best_model else None
    experiment.status = "completed" if completed_models else "failed"
    experiment.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.expire(experiment, ["models"])
    db.refresh(experiment)
    return experiment
