from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.config.settings import settings
from app.ml.explainer import explain_model
from app.models.experiment import Experiment, TrainedModel
from app.models.project import Project
from app.models.user import User


def _artifact_path(experiment_id: int, model_id: int) -> Path:
    root = Path(settings.MODEL_ARTIFACT_STORAGE_PATH).expanduser().resolve()
    destination = (root / f"experiment_{experiment_id}" / f"model_{model_id}.joblib").resolve()
    if destination.parent.parent != root:
        raise ValueError("Model artifact reference is invalid.")
    return destination


class ExplainabilityService:
    def __init__(self, db):
        self.db = db

    def get_owned_model(self, model_id: int, current_user: User) -> TrainedModel:
        model = (
            self.db.query(TrainedModel)
            .join(Experiment, Experiment.id == TrainedModel.experiment_id)
            .join(Project, Project.id == Experiment.project_id)
            .filter(TrainedModel.id == model_id, Project.user_id == current_user.id)
            .first()
        )
        if model is None:
            raise ValueError("Model not found.")
        return model

    def _load_dataset_frame(self, experiment: Experiment) -> pd.DataFrame:
        dataset = experiment.dataset
        if dataset is None:
            raise ValueError("The model's dataset is no longer available.")

        file_path = Path(dataset.file_path).expanduser()
        if not file_path.is_file():
            raise ValueError("The dataset file could not be found.")
        frame = pd.read_csv(file_path)
        frame.columns = [str(column).strip() for column in frame.columns]
        return frame

    def _load_pipeline(self, model: TrainedModel):
        artifact_file = _artifact_path(model.experiment_id, model.id)
        if not artifact_file.is_file():
            raise FileNotFoundError("Model artifact is missing.")
        return joblib.load(artifact_file)

    def build_response(self, model: TrainedModel) -> dict[str, Any]:
        experiment = model.experiment
        if experiment is None:
            raise ValueError("The model is no longer linked to an experiment.")
        if model.status != "completed":
            return {
                "model_id": model.id,
                "experiment_id": experiment.id,
                "algorithm": model.algorithm,
                "problem_type": experiment.problem_type,
                "status": "unsupported",
                "explanation_method": "none",
                "feature_importance": [],
                "local_explanation": None,
                "base_value": None,
                "prediction": None,
                "explanation_summary": "This model is not in a completed state and cannot be explained.",
                "limitations": ["Only successfully trained models can be explained."],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        try:
            pipeline = self._load_pipeline(model)
            frame = self._load_dataset_frame(experiment)
            if experiment.target_column and experiment.target_column in frame.columns:
                features = frame.drop(columns=[experiment.target_column])
            else:
                features = frame
            if features.empty:
                raise ValueError("No usable feature data found for this model.")

            raw_importance = explain_model(pipeline, model.algorithm, features, sample_size=min(len(features), 100))
            if isinstance(raw_importance, dict) and raw_importance.get("error") == "unsupported":
                return {
                    "model_id": model.id,
                    "experiment_id": experiment.id,
                    "algorithm": model.algorithm,
                    "problem_type": experiment.problem_type,
                    "status": "unsupported",
                    "explanation_method": "none",
                    "feature_importance": [],
                    "local_explanation": None,
                    "base_value": None,
                    "prediction": None,
                    "explanation_summary": raw_importance.get("message") or f"SHAP is unsupported for {model.algorithm}.",
                    "limitations": [
                        "This algorithm does not expose a safe SHAP explanation path.",
                        "The explanation is intentionally limited to deterministic, model-grounded metadata.",
                    ],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }

            feature_importance = []
            if isinstance(raw_importance, dict):
                for feature_name, value in sorted(raw_importance.items(), key=lambda item: float(item[1]), reverse=True):
                    score = float(value)
                    feature_importance.append(
                        {
                            "feature": feature_name,
                            "contribution": score,
                            "absolute_contribution": abs(score),
                            "direction": "positive" if score > 0 else "negative" if score < 0 else "neutral",
                            "metadata": {"source": "shap"},
                        }
                    )

            local_frame = features.iloc[:1].copy()
            local_prediction = pipeline.predict(local_frame).item() if hasattr(pipeline.predict(local_frame), "item") else pipeline.predict(local_frame)[0]
            summary = (
                f"{feature_importance[0]['feature']} had the strongest influence on the prediction in this {model.algorithm} model."
                if feature_importance
                else f"No feature-level SHAP contribution was available for {model.algorithm}."
            )
            fallback = "This explanation reflects statistical influence, not causal proof."
            return {
                "model_id": model.id,
                "experiment_id": experiment.id,
                "algorithm": model.algorithm,
                "problem_type": experiment.problem_type,
                "status": "completed",
                "explanation_method": "shap",
                "feature_importance": feature_importance,
                "local_explanation": feature_importance[:5],
                "base_value": float(np.mean([item["contribution"] for item in feature_importance])) if feature_importance else None,
                "prediction": float(local_prediction),
                "explanation_summary": summary,
                "limitations": [
                    "Model influence is not proof of causation.",
                    fallback,
                ],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # pragma: no cover - final error path is surfaced by tests and API
            return {
                "model_id": model.id,
                "experiment_id": experiment.id,
                "algorithm": model.algorithm,
                "problem_type": experiment.problem_type,
                "status": "unsupported",
                "explanation_method": "none",
                "feature_importance": [],
                "local_explanation": None,
                "base_value": None,
                "prediction": None,
                "explanation_summary": f"Explainability is unavailable for {model.algorithm}: {exc}",
                "limitations": [
                    "The explanation could not be generated from the persisted artifact.",
                    "No fabricated numerical explanation is provided.",
                ],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
