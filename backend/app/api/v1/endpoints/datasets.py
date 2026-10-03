import os
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.database.connection import get_db
from app.models.dataset import Dataset
from app.models.project import Project
from app.models.user import User
from app.schemas.dataset import DatasetDetail, DatasetRead, DatasetSummary
from app.services.dataset_service import analyze_csv_file, validate_dataset_upload
from app.services.storage import delete_dataset_file, save_uploaded_dataset

router = APIRouter()


def get_project_for_user(db: Session, project_id: int, current_user: User) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def get_dataset_for_user(db: Session, dataset_id: int, current_user: User) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    project = db.query(Project).filter(Project.id == dataset.project_id).first()
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


@router.post("/projects/{project_id}/datasets", response_model=DatasetDetail)
async def upload_dataset(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(db, project_id, current_user)
    if not file or not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A CSV file is required.")

    sample = await file.read(4096)
    await file.seek(0)
    try:
        validate_dataset_upload(file.filename, file.content_type, sample)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        storage_key, file_path, original_filename = save_uploaded_dataset(project.id, file)
        summary = analyze_csv_file(file_path)
    except ValueError as exc:
        if "file_path" in locals() and os.path.exists(file_path):
            delete_dataset_file(file_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if any(finding.get("type") in {"empty_dataset", "malformed_rows"} for finding in summary.get("findings", [])):
        delete_dataset_file(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded CSV is empty or has malformed rows and cannot be analyzed.",
        )

    dataset = Dataset(
        project_id=project.id,
        filename=original_filename,
        original_filename=original_filename,
        storage_key=storage_key,
        file_path=file_path,
        file_size=os.path.getsize(file_path),
        file_type="csv",
        row_count=summary["row_count"],
        column_count=summary["column_count"],
        status=summary.get("status", "ready") or "ready",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    response = DatasetRead.from_orm(dataset)
    response.summary = DatasetSummary(**summary)
    return response


@router.get("/projects/{project_id}/datasets", response_model=List[DatasetRead])
def list_project_datasets(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project_for_user(db, project_id, current_user)
    datasets = (
        db.query(Dataset)
        .filter(Dataset.project_id == project_id)
        .order_by(Dataset.uploaded_at.desc())
        .all()
    )
    return [DatasetRead.from_orm(dataset) for dataset in datasets]


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_dataset_for_user(db, dataset_id, current_user)
    summary = analyze_csv_file(dataset.file_path)
    response = DatasetRead.from_orm(dataset)
    response.summary = DatasetSummary(**summary)
    return response


@router.delete("/datasets/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_dataset_for_user(db, dataset_id, current_user)
    if os.path.exists(dataset.file_path):
        delete_dataset_file(dataset.file_path)

    db.delete(dataset)
    db.commit()
    return {"deleted": True, "dataset_id": dataset_id}
