from typing import Any

import optuna
from sklearn.metrics import f1_score, mean_squared_error, silhouette_score

from app.ml.algorithms import create_estimator
from app.ml.preprocessing import build_training_pipeline


def _parameters_for_trial(trial: optuna.Trial, problem_type: str, algorithm: str, train_row_count: int) -> dict[str, Any]:
    if algorithm == "Linear Regression":
        return {"fit_intercept": trial.suggest_categorical("fit_intercept", [True, False])}
    if algorithm == "Logistic Regression":
        return {"C": trial.suggest_float("C", 0.01, 10.0, log=True)}
    if algorithm in {"Random Forest", "Random Forest Regressor"}:
        return {
            "n_estimators": trial.suggest_int("n_estimators", 40, 140),
            "max_depth": trial.suggest_categorical("max_depth", [None, 3, 6, 10]),
            "min_samples_split": trial.suggest_int("min_samples_split", 2, 6),
        }
    if algorithm in {"Gradient Boosting", "Gradient Boosting Regressor"}:
        return {
            "n_estimators": trial.suggest_int("n_estimators", 40, 140),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 1, 4),
        }
    if problem_type == "clustering" and algorithm == "K-Means":
        if train_row_count < 3:
            raise ValueError("K-Means optimization requires at least three training rows.")
        return {
            "n_clusters": trial.suggest_int("n_clusters", 2, min(8, train_row_count - 1)),
            "n_init": trial.suggest_int("n_init", 5, 15),
        }
    raise ValueError("Optuna optimization is not available for this algorithm.")


def optimize_parameters(
    problem_type: str,
    algorithm: str,
    random_state: int,
    train_features,
    train_target,
    validation_features,
    validation_target,
    n_trials: int,
    timeout_seconds: int,
) -> tuple[dict[str, Any], float]:
    direction = "minimize" if problem_type == "regression" else "maximize"
    study = optuna.create_study(
        direction=direction,
        sampler=optuna.samplers.TPESampler(seed=random_state),
    )

    def objective(trial: optuna.Trial) -> float:
        parameters = _parameters_for_trial(trial, problem_type, algorithm, len(train_features))
        estimator = create_estimator(problem_type, algorithm, random_state, parameters)
        pipeline, _ = build_training_pipeline(train_features, estimator)
        pipeline.fit(train_features, train_target)
        if problem_type == "regression":
            prediction = pipeline.predict(validation_features)
            return float(mean_squared_error(validation_target, prediction) ** 0.5)
        if problem_type == "classification":
            prediction = pipeline.predict(validation_features)
            return float(f1_score(validation_target, prediction, average="macro", zero_division=0))

        preprocessor = pipeline.named_steps["preprocessing"]
        transformed_validation = preprocessor.transform(validation_features)
        estimator.fit(preprocessor.transform(train_features))
        validation_labels = estimator.predict(transformed_validation)
        unique_labels = set(validation_labels)
        if len(unique_labels) < 2 or len(unique_labels) >= len(validation_labels):
            return -1.0
        return float(silhouette_score(transformed_validation, validation_labels))

    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout_seconds,
        show_progress_bar=False,
        catch=(ValueError,),
    )
    if study.best_trial is None or not study.best_trial.params:
        raise ValueError("Optuna did not complete a valid hyperparameter trial.")
    return dict(study.best_params), float(study.best_value)
