from pathlib import Path

import mlflow

from app.config.settings import settings


def configure_tracking() -> None:
    if settings.MLFLOW_TRACKING_URI.strip():
        tracking_uri = settings.MLFLOW_TRACKING_URI.strip()
    else:
        tracking_path = Path(settings.MLFLOW_ARTIFACT_STORAGE_PATH).expanduser().resolve()
        tracking_path.mkdir(parents=True, exist_ok=True)
        tracking_uri = tracking_path.as_uri()
    mlflow.set_tracking_uri(tracking_uri)


def get_or_create_experiment(experiment_name: str) -> str:
    configure_tracking()
    return mlflow.set_experiment(experiment_name).experiment_id
