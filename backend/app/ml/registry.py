import os
from pathlib import Path

import joblib

from app.config.settings import settings


def artifact_path(experiment_id: int, model_id: int) -> Path:
    root = Path(settings.MODEL_ARTIFACT_STORAGE_PATH).expanduser().resolve()
    destination = (root / f"experiment_{experiment_id}" / f"model_{model_id}.joblib").resolve()
    if destination.parent.parent != root:
        raise ValueError("Model artifact reference is invalid.")
    return destination


def store_model(experiment_id: int, model_id: int, pipeline) -> str:
    path = artifact_path(experiment_id, model_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".joblib.tmp")
    try:
        joblib.dump(pipeline, temporary_path)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return f"experiment_{experiment_id}/model_{model_id}.joblib"
