import re
from pathlib import Path
from typing import Tuple
from uuid import uuid4

from fastapi import UploadFile

from app.config.settings import settings


def ensure_dataset_storage_root() -> Path:
    base_dir = Path(settings.DATASET_STORAGE_PATH).expanduser()
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def build_dataset_storage_path(project_id: int, original_filename: str) -> Tuple[str, str]:
    sanitized_name = Path(original_filename or "dataset.csv").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", sanitized_name) or "dataset.csv"
    if not safe_name.lower().endswith(".csv"):
        safe_name = f"{Path(safe_name).stem}.csv"

    storage_key = f"project_{project_id}_{uuid4().hex}_{safe_name}"
    destination_dir = ensure_dataset_storage_root() / f"project_{project_id}"
    destination_dir.mkdir(parents=True, exist_ok=True)
    file_path = destination_dir / storage_key
    return storage_key, str(file_path)


def save_uploaded_dataset(project_id: int, uploaded_file: UploadFile) -> Tuple[str, str, str]:
    if uploaded_file.filename is None or uploaded_file.filename.strip() == "":
        raise ValueError("A filename is required for the dataset upload.")

    storage_key, file_path = build_dataset_storage_path(project_id, uploaded_file.filename)
    with open(file_path, "wb") as destination:
        while True:
            chunk = uploaded_file.file.read(1024 * 1024)
            if not chunk:
                break
            destination.write(chunk)

    return storage_key, file_path, uploaded_file.filename


def resolve_dataset_storage_path(project_id: int, storage_key: str) -> Path:
    if not storage_key or Path(storage_key).name != storage_key or "/" in storage_key or "\\" in storage_key:
        raise ValueError("Dataset storage reference is invalid.")

    storage_root = ensure_dataset_storage_root().resolve()
    project_dir = (storage_root / f"project_{project_id}").resolve()
    if project_dir.parent != storage_root:
        raise ValueError("Dataset storage reference is invalid.")
    dataset_path = (project_dir / storage_key).resolve()
    if dataset_path.parent != project_dir or not dataset_path.is_file():
        raise ValueError("Dataset file could not be found in managed storage.")
    return dataset_path


def delete_dataset_file(file_path: str) -> None:
    file_reference = Path(file_path)
    if file_reference.exists() and file_reference.is_file():
        file_reference.unlink()
