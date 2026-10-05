import io
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.settings import settings
from app.database.connection import get_db
from app.main import app
from app.models.base import Base
from app.models.dataset import Dataset
from app.models.project import Project
from app.models.user import User
from app.services.storage import save_uploaded_dataset

SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def register_user(client, email="user@example.com", password="StrongPass123"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def login_token(client, email="user@example.com", password="StrongPass123"):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def create_project(client, user_email="user@example.com", **kwargs):
    token = login_token(client, user_email)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "name": "Customer Retention",
        "problem_statement": "Predict whether customers will churn.",
        "objective": "Reduce churn and improve retention.",
        "mode": "engineering",
    }
    payload.update(kwargs)
    response = client.post("/api/v1/projects", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json(), headers


def create_dataset_record(project_id, file_bytes: bytes, name: str = "sample.csv"):
    storage_root = settings.DATASET_STORAGE_PATH
    os.makedirs(storage_root, exist_ok=True)
    upload_file = io.BytesIO(file_bytes)
    upload_file.name = name
    storage_key, file_path, original_filename = save_uploaded_dataset(project_id, type("UploadedFile", (), {"filename": name, "file": upload_file})())
    dataset = Dataset(
        project_id=project_id,
        filename=original_filename,
        original_filename=original_filename,
        storage_key=storage_key,
        file_path=file_path,
        file_size=len(file_bytes),
        file_type="csv",
        row_count=6,
        column_count=3,
        status="ready",
    )
    db = TestingSessionLocal()
    try:
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return dataset
    finally:
        db.close()


def test_recommendation_endpoint_classifies_problem_and_returns_schema(client):
    register_user(client)
    project, headers = create_project(client)
    csv_payload = b"customer_id,age,churn\n1,25,0\n2,30,1\n3,35,0\n4,40,1\n5,45,0\n6,50,1\n"
    create_dataset_record(project["id"], csv_payload)

    response = client.post(f"/api/v1/projects/{project['id']}/recommend", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["problem_type"] == "classification"
    assert body["recommended_pipeline"]
    assert body["candidate_algorithms"]
    assert body["preprocessing_steps"]
    assert "/api/v1" not in body["explanation"]


def test_recommendation_endpoint_handles_unknown_problem_safely(client):
    register_user(client)
    project, headers = create_project(
        client,
        name="Research Discovery",
        problem_statement="We need to explore the dataset and find patterns.",
        objective="Understand the structure of the data.",
    )
    csv_payload = b"feature_a,feature_b\n1,2\n2,3\n3,4\n"
    create_dataset_record(project["id"], csv_payload)

    response = client.post(f"/api/v1/projects/{project['id']}/recommend", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["problem_type"] in {"unknown", "clustering"}
    assert body["warnings"]
    assert body["recommended_pipeline"]
