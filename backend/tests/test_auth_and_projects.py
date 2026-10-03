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


def test_problem_update_persists_on_project(client):
    register_user(client)
    headers = auth_headers(client)
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Problem Project",
            "problem_statement": "Old problem",
            "objective": "Old objective",
            "mode": "engineering",
        },
        headers=headers,
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "problem_statement": "Updated problem statement",
            "objective": "Updated objective",
            "mode": "learning",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["problem_statement"] == "Updated problem statement"
    assert response.json()["objective"] == "Updated objective"
    assert response.json()["mode"] == "learning"


def test_upload_valid_csv_dataset(client):
    register_user(client)
    headers = auth_headers(client)
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Dataset Project",
            "problem_statement": "Need a dataset.",
            "objective": "Analyze quality.",
            "mode": "engineering",
        },
        headers=headers,
    ).json()

    csv_content = b"age,city,score\n30,Paris,10\n,London,20\n45,,30\n"
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("customers.csv", csv_content, "text/csv")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["filename"] == "customers.csv"
    assert body["status"] in {"ready", "ready_with_warnings"}
    assert body["row_count"] == 3
    assert body["column_count"] == 3


def test_reject_unauthenticated_dataset_upload(client):
    register_user(client)
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Dataset Project",
            "problem_statement": "Need a dataset.",
            "objective": "Analyze quality.",
            "mode": "engineering",
        },
        headers=auth_headers(client),
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("customers.csv", b"name\nAlice\n", "text/csv")},
    )
    assert response.status_code == 401


def test_reject_dataset_upload_to_other_users_project(client):
    register_user(client, email="one@example.com")
    register_user(client, email="two@example.com")
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Other user project",
            "problem_statement": "Not mine",
            "objective": "Nope",
            "mode": "engineering",
        },
        headers=auth_headers(client, email="one@example.com"),
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("customers.csv", b"name\nAlice\n", "text/csv")},
        headers=auth_headers(client, email="two@example.com"),
    )
    assert response.status_code == 404


def test_reject_unsupported_file_type(client):
    register_user(client)
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Dataset Project",
            "problem_statement": "Need a dataset.",
            "objective": "Analyze quality.",
            "mode": "engineering",
        },
        headers=auth_headers(client),
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("customers.xlsx", b"PK\x03\x04fake", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers(client),
    )
    assert response.status_code == 400


def test_empty_csv_dataset_is_handled(client):
    register_user(client)
    headers = auth_headers(client)
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Dataset Project",
            "problem_statement": "Need a dataset.",
            "objective": "Analyze quality.",
            "mode": "engineering",
        },
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("empty.csv", b"", "text/csv")},
        headers=headers,
    )
    assert response.status_code == 400


def test_malformed_csv_dataset_is_rejected(client):
    register_user(client)
    headers = auth_headers(client)
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Dataset Project",
            "problem_statement": "Need a dataset.",
            "objective": "Analyze quality.",
            "mode": "engineering",
        },
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("broken.csv", b"name,age\nAlice,30,extra\n", "text/csv")},
        headers=headers,
    )
    assert response.status_code == 400


def test_list_and_get_dataset(client):
    register_user(client)
    headers = auth_headers(client)
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Dataset Project",
            "problem_statement": "Need a dataset.",
            "objective": "Analyze quality.",
            "mode": "engineering",
        },
        headers=headers,
    ).json()

    upload = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("customers.csv", b"age,city\n30,Paris\n,London\n", "text/csv")},
        headers=headers,
    )
    dataset_id = upload.json()["id"]

    list_response = client.get(f"/api/v1/projects/{project['id']}/datasets", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail = client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["filename"] == "customers.csv"
    assert detail.json()["summary"]["duplicate_rows"] >= 0


def test_delete_own_dataset(client):
    register_user(client)
    headers = auth_headers(client)
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Dataset Project",
            "problem_statement": "Need a dataset.",
            "objective": "Analyze quality.",
            "mode": "engineering",
        },
        headers=headers,
    ).json()

    upload = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("customers.csv", b"age,city\n30,Paris\n", "text/csv")},
        headers=headers,
    )
    dataset_id = upload.json()["id"]

    response = client.delete(f"/api/v1/datasets/{dataset_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_reject_another_users_dataset_access(client):
    register_user(client, email="first@example.com")
    register_user(client, email="second@example.com")
    headers_first = auth_headers(client, email="first@example.com")
    headers_second = auth_headers(client, email="second@example.com")
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "First Project",
            "problem_statement": "Owned by first",
            "objective": "Goal",
            "mode": "engineering",
        },
        headers=headers_first,
    ).json()
    dataset = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("customers.csv", b"age\n30\n", "text/csv")},
        headers=headers_first,
    ).json()

    assert client.get(f"/api/v1/datasets/{dataset['id']}", headers=headers_second).status_code == 404
    assert client.delete(f"/api/v1/datasets/{dataset['id']}", headers=headers_second).status_code == 404
