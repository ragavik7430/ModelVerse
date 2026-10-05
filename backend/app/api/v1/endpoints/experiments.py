import hashlib
import io
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.agents import execute_agent_graph
from app.api.v1.endpoints.auth import get_current_user
from app.config.settings import settings
from app.database.connection import get_db
from app.ml import run_experiment
from app.ml.algorithms import supported_recommendations
from app.ml.trainer import validate_training_frame
from app.models.dataset import Dataset
from app.models.experiment import Experiment
from app.models.project import Project
from app.models.user import User
from app.schemas.experiment import ExperimentComparisonRead, ExperimentCreate, ExperimentRead
from app.services.dataset_service import analyze_csv_file
from app.services.storage import resolve_dataset_storage_path


logger = logging.getLogger(__name__)
router = APIRouter()


def _raise_error(status_code: int, code: str, message: str):
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _project_for_user(db: Session, project_id: int, current_user: User) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if project is None:
        _raise_error(status.HTTP_404_NOT_FOUND, "project_not_found", "Project not found.")
    return project


def _dataset_for_project(db: Session, project_id: int, dataset_id: int) -> Dataset:
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.project_id == project_id)
        .first()
    )
    if dataset is None:
        _raise_error(status.HTTP_404_NOT_FOUND, "dataset_not_found", "Dataset not found for this project.")
    return dataset


def _dataset_path(dataset: Dataset):
    try:
        return resolve_dataset_storage_path(dataset.project_id, dataset.storage_key)
    except ValueError as exc:
        raise ValueError("Dataset storage reference is invalid.") from exc


def _load_dataset_frame(dataset: Dataset) -> tuple[pd.DataFrame, str]:
    path = _dataset_path(dataset)
    try:
        content = path.read_bytes()
        frame = pd.read_csv(io.BytesIO(content))
    except (OSError, UnicodeError, pd.errors.ParserError, ValueError) as exc:
        raise ValueError("The selected dataset could not be read as a valid CSV.") from exc
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame, hashlib.sha256(content).hexdigest()


def _phase4_recommendation(project: Project, dataset: Dataset) -> dict:
    path = _dataset_path(dataset)
    try:
        summary = analyze_csv_file(str(path))
        recommendation = execute_agent_graph(
            {
                "project_id": project.id,
                "project_name": project.name,
                "problem_statement": project.problem_statement,
                "objective": project.objective,
                "dataset_id": dataset.id,
                "dataset_summary": summary,
                "problem_type": "unknown",
                "target_candidate": None,
                "feature_candidates": list(summary.get("columns") or []),
                "dataset_characteristics": {},
                "recommended_pipeline": "",
                "candidate_algorithms": [],
                "preprocessing_steps": [],
                "rationale": "",
                "confidence": 0.0,
                "warnings": [],
                "explanation": "",
                "errors": [],
            }
        )
    except (OSError, ValueError) as exc:
        raise ValueError("Phase 4 could not analyze the selected dataset.") from exc
    except Exception as exc:
        logger.exception("Phase 4 recommendation failed while creating an experiment.")
        raise RuntimeError("The project recommendation could not be verified.") from exc

    if not isinstance(recommendation, dict):
        raise RuntimeError("The project recommendation could not be verified.")
    return recommendation


def _experiment_for_user(db: Session, experiment_id: int, current_user: User) -> Experiment:
    experiment = (
        db.query(Experiment)
        .options(joinedload(Experiment.models))
        .join(Project, Experiment.project_id == Project.id)
        .filter(Experiment.id == experiment_id, Project.user_id == current_user.id)
        .first()
    )
    if experiment is None:
        _raise_error(status.HTTP_404_NOT_FOUND, "experiment_not_found", "Experiment not found.")
    return experiment


def _run_saved_experiment(db: Session, experiment: Experiment, operation: str) -> Experiment:
    if experiment.status != "queued":
        _raise_error(status.HTTP_409_CONFLICT, "experiment_already_started", "This experiment has already started. Create a new experiment to train again.")
    if bool(experiment.configuration.get("optimize")) != (operation == "optimize"):
        _raise_error(status.HTTP_409_CONFLICT, "operation_mismatch", "Use the endpoint that matches the experiment training mode.")

    dataset = db.query(Dataset).filter(
        Dataset.id == experiment.dataset_id,
        Dataset.project_id == experiment.project_id,
    ).first()
    if dataset is None:
        experiment.status = "failed"
        experiment.error_message = "The dataset is no longer available."
        experiment.completed_at = datetime.now(timezone.utc)
        db.commit()
        _raise_error(status.HTTP_409_CONFLICT, "dataset_unavailable", "The dataset is no longer available.")

    experiment.status = "running"
    experiment.started_at = datetime.now(timezone.utc)
    db.commit()
    try:
        frame, dataset_sha256 = _load_dataset_frame(dataset)
        if dataset_sha256 != experiment.configuration.get("dataset_sha256"):
            raise ValueError("The dataset contents changed after this experiment was configured. Create a new experiment.")
        return run_experiment(
            db,
            experiment,
            frame,
            allow_identifier_target=bool(experiment.configuration.get("allow_identifier_target")),
        )
    except ValueError as exc:
        db.rollback()
        experiment = db.query(Experiment).filter(Experiment.id == experiment.id).first()
        experiment.status = "failed"
        experiment.error_message = str(exc)
        experiment.completed_at = datetime.now(timezone.utc)
        db.commit()
        _raise_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "training_validation_failed", str(exc))
    except Exception as exc:
        logger.exception("Experiment execution failed (experiment_id=%s).", experiment.id)
        db.rollback()
        experiment = db.query(Experiment).filter(Experiment.id == experiment.id).first()
        experiment.status = "failed"
        experiment.error_message = "Experiment execution failed. Check the server log for details."
        experiment.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "experiment_execution_failed", "message": experiment.error_message},
        ) from exc


@router.post("/projects/{project_id}/experiments", response_model=ExperimentRead, status_code=status.HTTP_201_CREATED)
def create_experiment(
    project_id: int,
    payload: ExperimentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _project_for_user(db, project_id, current_user)
    dataset = _dataset_for_project(db, project_id, payload.dataset_id)
    if not dataset.storage_key:
        _raise_error(status.HTTP_400_BAD_REQUEST, "invalid_dataset_storage", "Dataset storage reference is invalid.")

    try:
        frame, dataset_sha256 = _load_dataset_frame(dataset)
        recommendation = _phase4_recommendation(project, dataset)
        validate_training_frame(
            frame,
            SimpleNamespace(problem_type=payload.problem_type, target_column=payload.target_column),
            allow_identifier_target=payload.allow_identifier_target,
        )
    except ValueError as exc:
        _raise_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "training_validation_failed", str(exc))
    except RuntimeError as exc:
        _raise_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "recommendation_unavailable", str(exc))

    recommended_type = recommendation.get("problem_type", "unknown")
    if payload.problem_type != recommended_type:
        _raise_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "problem_type_mismatch", "The selected problem type must match the current Phase 4 recommendation.")
    recommended_algorithms = supported_recommendations(
        recommended_type,
        recommendation.get("candidate_algorithms") or [],
    )
    if not recommended_algorithms:
        _raise_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "no_supported_candidates", "Phase 4 did not recommend a supported training candidate for this problem.")
    if any(algorithm not in recommended_algorithms for algorithm in payload.selected_algorithms):
        _raise_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "unsupported_algorithm", "Select only supported algorithms proposed by the current Phase 4 recommendation.")
    if payload.optimize:
        try:
            if not 1 <= settings.OPTUNA_N_TRIALS <= 20:
                raise ValueError("OPTUNA_N_TRIALS must be between 1 and 20.")
            if not 1 <= settings.OPTUNA_TIMEOUT_SECONDS <= 600:
                raise ValueError("OPTUNA_TIMEOUT_SECONDS must be between 1 and 600.")
        except ValueError as exc:
            _raise_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "optimizer_configuration_error", str(exc))

    experiment = Experiment(
        project_id=project.id,
        dataset_id=dataset.id,
        problem_type=payload.problem_type,
        target_column=payload.target_column,
        experiment_name=f"{project.name} experiment",
        status="queued",
        random_state=payload.random_state,
        test_size=payload.test_size,
        configuration={
            "selected_algorithms": payload.selected_algorithms,
            "recommended_algorithms": recommended_algorithms,
            "target_confirmed": payload.target_confirmed,
            "allow_identifier_target": payload.allow_identifier_target,
            "optimize": payload.optimize,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "dataset_id_snapshot": dataset.id,
            "dataset_sha256": dataset_sha256,
        },
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


@router.post("/experiments/{experiment_id}/train", response_model=ExperimentRead)
def train_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    experiment = _experiment_for_user(db, experiment_id, current_user)
    return _run_saved_experiment(db, experiment, "train")


@router.post("/experiments/{experiment_id}/optimize", response_model=ExperimentRead)
def optimize_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    experiment = _experiment_for_user(db, experiment_id, current_user)
    return _run_saved_experiment(db, experiment, "optimize")


@router.get("/projects/{project_id}/experiments", response_model=list[ExperimentRead])
def list_project_experiments(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _project_for_user(db, project_id, current_user)
    return (
        db.query(Experiment)
        .options(joinedload(Experiment.models))
        .filter(Experiment.project_id == project_id)
        .order_by(Experiment.created_at.desc())
        .all()
    )


@router.get("/experiments/{experiment_id}", response_model=ExperimentRead)
def get_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _experiment_for_user(db, experiment_id, current_user)


@router.get("/experiments/{experiment_id}/comparison", response_model=ExperimentComparisonRead)
def compare_experiment_models(
    experiment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    experiment = _experiment_for_user(db, experiment_id, current_user)
    return {
        "experiment_id": experiment.id,
        "status": experiment.status,
        "problem_type": experiment.problem_type,
        "comparison_policy": experiment.comparison_policy,
        "best_model_id": experiment.best_model_id,
        "candidates": experiment.models,
    }
