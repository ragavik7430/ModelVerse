import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import get_db
from app.main import app
from app.models.base import Base

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
    data = response.json()
    assert data["email"] == email
    return data


def login_user(client, email="user@example.com", password="StrongPass123"):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


def auth_headers(client, email="user@example.com", password="StrongPass123"):
    token = login_user(client, email=email, password=password)
    return {"Authorization": f"Bearer {token}"}


def test_register_valid_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "user@example.com"
    assert "password_hash" not in body
    assert "password" not in body


def test_duplicate_email_rejected(client):
    register_user(client)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 409


def test_invalid_email_rejected(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "StrongPass123"},
    )
    assert response.status_code == 422


def test_weak_password_rejected(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_login_valid_credentials(client):
    register_user(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_invalid_credentials(client):
    register_user(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "WrongPassword123"},
    )
    assert response.status_code == 401


def test_get_current_user_authenticated(client):
    register_user(client)
    headers = auth_headers(client)
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_get_current_user_unauthenticated(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_create_project_authenticated(client):
    register_user(client)
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Website Conversion Forecast",
            "problem_statement": "We want to predict churn before users leave the funnel.",
            "objective": "Improve retention with better forecasting.",
            "mode": "engineering",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Website Conversion Forecast"
    assert body["status"] == "Created"


def test_create_project_unauthenticated(client):
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Website Conversion Forecast",
            "problem_statement": "We want to predict churn before users leave the funnel.",
            "objective": "Improve retention with better forecasting.",
            "mode": "engineering",
        },
    )
    assert response.status_code == 401


def test_list_users_projects(client):
    register_user(client)
    headers = auth_headers(client)
    client.post(
        "/api/v1/projects",
        json={
            "name": "Project A",
            "problem_statement": "Problem A",
            "objective": "Objective A",
            "mode": "engineering",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/projects",
        json={
            "name": "Project B",
            "problem_statement": "Problem B",
            "objective": "Objective B",
            "mode": "learning",
        },
        headers=headers,
    )
    response = client.get("/api/v1/projects", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_project_ownership_isolation(client):
    register_user(client, email="user1@example.com")
    register_user(client, email="user2@example.com")
    headers1 = auth_headers(client, email="user1@example.com")
    headers2 = auth_headers(client, email="user2@example.com")

    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "User 1 Project",
            "problem_statement": "Owned by user 1",
            "objective": "Goal for user 1",
            "mode": "engineering",
        },
        headers=headers1,
    )
    project_id = create_response.json()["id"]

    response = client.get(f"/api/v1/projects/{project_id}", headers=headers2)
    assert response.status_code == 404


def test_get_own_project(client):
    register_user(client)
    headers = auth_headers(client)
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "My Project",
            "problem_statement": "Problem statement",
            "objective": "Objective statement",
            "mode": "learning",
        },
        headers=headers,
    )
    project_id = create_response.json()["id"]
    response = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "My Project"


def test_reject_another_users_project(client):
    register_user(client, email="first@example.com")
    register_user(client, email="second@example.com")
    headers1 = auth_headers(client, email="first@example.com")
    headers2 = auth_headers(client, email="second@example.com")
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "First Project",
            "problem_statement": "Only first user should see this.",
            "objective": "Goal",
            "mode": "engineering",
        },
        headers=headers1,
    )
    project_id = create_response.json()["id"]
    response = client.patch(f"/api/v1/projects/{project_id}", json={"name": "Hacked"}, headers=headers2)
    assert response.status_code == 404


def test_update_own_project(client):
    register_user(client)
    headers = auth_headers(client)
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Original Project",
            "problem_statement": "Original problem",
            "objective": "Original objective",
            "mode": "engineering",
        },
        headers=headers,
    )
    project_id = create_response.json()["id"]
    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated Project", "mode": "learning"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Project"
    assert response.json()["mode"] == "learning"


def test_delete_own_project(client):
    register_user(client)
    headers = auth_headers(client)
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Delete Me",
            "problem_statement": "This should vanish",
            "objective": "Delete objective",
            "mode": "engineering",
        },
        headers=headers,
    )
    project_id = create_response.json()["id"]
    response = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_invalid_project_mode_rejected(client):
    register_user(client)
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Invalid Mode Project",
            "problem_statement": "Problem statement",
            "objective": "Objective statement",
            "mode": "invalid-mode",
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 422
