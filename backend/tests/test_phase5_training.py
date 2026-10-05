import io
from pathlib import Path

import mlflow
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.settings import settings
from app.database.connection import get_db
from app.main import app
from app.models.base import Base


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_db(tmp_path, monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "DATASET_STORAGE_PATH", str(tmp_path / "datasets"))
    monkeypatch.setattr(settings, "MODEL_ARTIFACT_STORAGE_PATH", str(tmp_path / "models"))
    monkeypatch.setattr(settings, "MLFLOW_ARTIFACT_STORAGE_PATH", str(tmp_path / "mlruns"))
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "")
    monkeypatch.setattr(settings, "OPTUNA_N_TRIALS", 2)
    monkeypatch.setattr(settings, "OPTUNA_TIMEOUT_SECONDS", 20)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


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


def _register_and_auth(client, email="phase5@example.com"):
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123"},
    )
    assert registered.status_code == 200, registered.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_project_and_dataset(client, headers, problem, objective, csv_text):
    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Phase 5 Training",
            "problem_statement": problem,
            "objective": objective,
            "mode": "engineering",
        },
    )
    assert project_response.status_code == 200, project_response.text
    project = project_response.json()
    upload_response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        headers=headers,
        files={"file": ("training.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
    )
    assert upload_response.status_code == 200, upload_response.text
    return project, upload_response.json()


def _regression_csv():
    lines = ["age,experience,department,salary"]
    for row in range(24):
        age = "" if row == 3 else str(21 + row)
        experience = str(row % 9)
        department = "" if row == 5 else ("engineering" if row % 2 == 0 else "analytics")
        salary = 24000 + row * 1750
        lines.append(f"{age},{experience},{department},{salary}")
    return "\n".join(lines) + "\n"


def _create_training_request(project, dataset, algorithms, optimize=False):
    return {
        "dataset_id": dataset["id"],
        "problem_type": "regression",
        "target_column": "salary",
        "target_confirmed": True,
        "selected_algorithms": algorithms,
        "test_size": 0.2,
        "random_state": 42,
        "optimize": optimize,
    }


def test_regression_experiment_trains_compares_tracks_and_persists(client):
    headers = _register_and_auth(client)
    project, dataset = _create_project_and_dataset(
        client,
        headers,
        "Estimate employee salary from age, department, and experience.",
        "Predict the continuous salary value.",
        _regression_csv(),
    )
    recommendation = client.post(f"/api/v1/projects/{project['id']}/recommend", headers=headers)
    assert recommendation.status_code == 200, recommendation.text
    assert recommendation.json()["problem_type"] == "regression"

    created = client.post(
        f"/api/v1/projects/{project['id']}/experiments",
        headers=headers,
        json=_create_training_request(project, dataset, ["Linear Regression", "Random Forest Regressor"]),
    )
    assert created.status_code == 201, created.text
    experiment_id = created.json()["id"]
    trained = client.post(f"/api/v1/experiments/{experiment_id}/train", headers=headers)
    assert trained.status_code == 200, trained.text
    experiment = trained.json()
    assert experiment["status"] == "completed"
    assert len(experiment["models"]) == 2
    assert all(model["status"] == "completed" for model in experiment["models"])
    assert all(model["mlflow_run_id"] for model in experiment["models"])
    assert all(model["metrics"]["test"]["rmse"] is not None for model in experiment["models"])
    assert all(model["metrics"]["validation"]["mae"] is not None for model in experiment["models"])
    assert all(model["preprocessing"]["fit_scope"] == "training split only" for model in experiment["models"])
    assert experiment["best_model_id"] in [model["id"] for model in experiment["models"]]
    assert len(experiment["configuration"]["dataset_sha256"]) == 64
    assert sum(experiment["configuration"]["split_row_counts"].values()) == 24
    for model in experiment["models"]:
        artifact_file = (
            Path(settings.MODEL_ARTIFACT_STORAGE_PATH)
            / f"experiment_{experiment_id}"
            / f"model_{model['id']}.joblib"
        )
        assert artifact_file.is_file()
        assert "artifact_key" not in model

    mlflow.set_tracking_uri(Path(settings.MLFLOW_ARTIFACT_STORAGE_PATH).resolve().as_uri())
    tracked_run = mlflow.get_run(experiment["models"][0]["mlflow_run_id"])
    assert tracked_run.data.tags["modelverse.dataset_id"] == str(dataset["id"])
    assert "test.rmse" in tracked_run.data.metrics

    comparison = client.get(f"/api/v1/experiments/{experiment_id}/comparison", headers=headers)
    assert comparison.status_code == 200, comparison.text
    assert len(comparison.json()["candidates"]) == 2
    assert "Lowest validation RMSE" in comparison.json()["comparison_policy"]

    history = client.get(f"/api/v1/projects/{project['id']}/experiments", headers=headers)
    assert history.status_code == 200, history.text
    assert history.json()[0]["id"] == experiment_id
    assert history.json()[0]["models"][0]["mlflow_run_id"]


def test_linear_regression_with_optuna_completes(client):
    headers = _register_and_auth(client)
    project, dataset = _create_project_and_dataset(
        client,
        headers,
        "Estimate employee salary from age, department, and experience.",
        "Predict the continuous salary value.",
        _regression_csv(),
    )
    created = client.post(
        f"/api/v1/projects/{project['id']}/experiments",
        headers=headers,
        json=_create_training_request(
            project,
            dataset,
            ["Linear Regression", "Random Forest Regressor", "Gradient Boosting Regressor"],
            optimize=True,
        ),
    )
    assert created.status_code == 201, created.text

    trained = client.post(f"/api/v1/experiments/{created.json()['id']}/optimize", headers=headers)

    assert trained.status_code == 200, trained.text
    experiment = trained.json()
    assert experiment["status"] == "completed"
    models = {model["algorithm"]: model for model in experiment["models"]}
    assert set(models) == {"Linear Regression", "Random Forest Regressor", "Gradient Boosting Regressor"}
    assert all(model["status"] == "completed" for model in models.values())
    assert all(model["mlflow_run_id"] for model in models.values())

    model = models["Linear Regression"]
    assert model["algorithm"] == "Linear Regression"
    assert model["status"] == "completed"
    assert model["metrics"]["optimization"]["n_trials"] == 2
    assert model["metrics"]["optimization"]["best_parameters"]
    assert model["metrics"]["optimization"]["best_parameters"]["fit_intercept"] in (True, False)
    assert model["parameters"]["fit_intercept"] == model["metrics"]["optimization"]["best_parameters"]["fit_intercept"]
    assert model["metrics"]["validation"]["rmse"] is not None
    assert model["metrics"]["test"]["rmse"] is not None
    assert models["Random Forest Regressor"]["metrics"]["optimization"]["best_parameters"]
    assert models["Gradient Boosting Regressor"]["metrics"]["optimization"]["best_parameters"]


def test_classification_training_and_optuna_are_deterministic(client):
    headers = _register_and_auth(client)
    rows = ["age,department,churn"]
    for row in range(30):
        rows.append(f"{20 + row},{'sales' if row % 2 else 'engineering'},{row % 2}")
    project, dataset = _create_project_and_dataset(
        client,
        headers,
        "Classify customer churn risk.",
        "Predict whether a customer will cancel.",
        "\n".join(rows) + "\n",
    )
    payload = {
        "dataset_id": dataset["id"],
        "problem_type": "classification",
        "target_column": "churn",
        "target_confirmed": True,
        "selected_algorithms": ["Logistic Regression"],
        "test_size": 0.2,
        "random_state": 19,
        "optimize": True,
    }
    created = client.post(f"/api/v1/projects/{project['id']}/experiments", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    result = client.post(f"/api/v1/experiments/{created.json()['id']}/optimize", headers=headers)
    assert result.status_code == 200, result.text
    model = result.json()["models"][0]
    assert model["status"] == "completed"
    assert model["metrics"]["test"]["f1_macro"] is not None
    assert model["metrics"]["test"]["confusion_matrix"]
    assert model["metrics"]["optimization"]["n_trials"] == 2
    assert model["metrics"]["optimization"]["random_state"] == 19
    assert model["parameters"]["C"] == model["metrics"]["optimization"]["best_parameters"]["C"]


def test_clustering_training_runs_without_a_target(client):
    headers = _register_and_auth(client)
    rows = ["x,y"]
    for row in range(24):
        base = 0 if row < 12 else 10
        rows.append(f"{base + row % 4 / 10},{base + row % 5 / 10}")
    project, dataset = _create_project_and_dataset(
        client,
        headers,
        "Cluster these records to discover natural groups.",
        "Find similar groups without a labeled outcome.",
        "\n".join(rows) + "\n",
    )
    created = client.post(
        f"/api/v1/projects/{project['id']}/experiments",
        headers=headers,
        json={
            "dataset_id": dataset["id"],
            "problem_type": "clustering",
            "target_column": None,
            "selected_algorithms": ["K-Means"],
            "test_size": 0.2,
            "random_state": 42,
            "optimize": False,
        },
    )
    assert created.status_code == 201, created.text
    trained = client.post(f"/api/v1/experiments/{created.json()['id']}/train", headers=headers)
    assert trained.status_code == 200, trained.text
    model = trained.json()["models"][0]
    assert model["status"] == "completed"
    assert model["metrics"]["test"]["silhouette"] is not None


def test_invalid_targets_algorithms_and_cross_user_access_are_rejected(client):
    headers = _register_and_auth(client, "owner@example.com")
    project, dataset = _create_project_and_dataset(
        client,
        headers,
        "Estimate employee salary.",
        "Forecast the continuous salary value.",
        _regression_csv(),
    )
    base_payload = _create_training_request(project, dataset, ["Linear Regression"])

    missing_target = {**base_payload, "target_column": "not_a_column"}
    response = client.post(f"/api/v1/projects/{project['id']}/experiments", headers=headers, json=missing_target)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "training_validation_failed"

    unsupported = {**base_payload, "selected_algorithms": ["Arbitrary Python Estimator"]}
    response = client.post(f"/api/v1/projects/{project['id']}/experiments", headers=headers, json=unsupported)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_algorithm"

    unauthenticated = client.post(
        f"/api/v1/projects/{project['id']}/experiments",
        json=base_payload,
    )
    assert unauthenticated.status_code == 401

    created = client.post(f"/api/v1/projects/{project['id']}/experiments", headers=headers, json=base_payload)
    assert created.status_code == 201, created.text
    other_user_headers = _register_and_auth(client, "other@example.com")
    foreign_project = client.post(
        f"/api/v1/projects/{project['id']}/experiments",
        headers=other_user_headers,
        json=base_payload,
    )
    assert foreign_project.status_code == 404
    hidden = client.get(f"/api/v1/experiments/{created.json()['id']}", headers=other_user_headers)
    assert hidden.status_code == 404


def test_identifier_target_requires_explicit_allowance(client):
    headers = _register_and_auth(client)
    rows = ["record_id,age,salary"]
    for row in range(12):
        rows.append(f"{1000 + row},{20 + row},{30000 + row * 100}")
    project, dataset = _create_project_and_dataset(
        client,
        headers,
        "Estimate employee salary.",
        "Predict a continuous salary value.",
        "\n".join(rows) + "\n",
    )
    payload = _create_training_request(project, dataset, ["Linear Regression"])
    payload["target_column"] = "record_id"
    rejected = client.post(f"/api/v1/projects/{project['id']}/experiments", headers=headers, json=payload)
    assert rejected.status_code == 422
    assert "identifier" in rejected.json()["detail"]["message"].lower()

    payload["allow_identifier_target"] = True
    accepted = client.post(f"/api/v1/projects/{project['id']}/experiments", headers=headers, json=payload)
    assert accepted.status_code == 201, accepted.text


def test_classification_rejects_a_likely_continuous_numeric_target(client):
    headers = _register_and_auth(client)
    project, dataset = _create_project_and_dataset(
        client,
        headers,
        "Classify employees into discrete salary groups.",
        "Assign a category label from employee data.",
        _regression_csv(),
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/experiments",
        headers=headers,
        json={
            "dataset_id": dataset["id"],
            "problem_type": "classification",
            "target_column": "salary",
            "target_confirmed": True,
            "selected_algorithms": ["Logistic Regression"],
            "test_size": 0.2,
            "random_state": 42,
            "optimize": False,
        },
    )
    assert response.status_code == 422
    assert "discrete class target" in response.json()["detail"]["message"]


def test_dataset_changes_after_configuration_are_rejected(client):
    headers = _register_and_auth(client)
    project, dataset = _create_project_and_dataset(
        client,
        headers,
        "Estimate employee salary.",
        "Predict the continuous salary value.",
        _regression_csv(),
    )
    created = client.post(
        f"/api/v1/projects/{project['id']}/experiments",
        headers=headers,
        json=_create_training_request(project, dataset, ["Linear Regression"]),
    )
    assert created.status_code == 201, created.text
    dataset_files = list((Path(settings.DATASET_STORAGE_PATH) / f"project_{project['id']}").glob("*.csv"))
    assert len(dataset_files) == 1
    dataset_files[0].write_text(dataset_files[0].read_text(encoding="utf-8") + "45,13,AI,86000\n", encoding="utf-8")

    result = client.post(f"/api/v1/experiments/{created.json()['id']}/train", headers=headers)
    assert result.status_code == 422
    assert "contents changed" in result.json()["detail"]["message"]


def test_failed_candidate_does_not_abort_other_candidates(client, monkeypatch):
    from app.ml import trainer

    headers = _register_and_auth(client)
    project, dataset = _create_project_and_dataset(
        client,
        headers,
        "Estimate employee salary.",
        "Predict the continuous salary value.",
        _regression_csv(),
    )
    created = client.post(
        f"/api/v1/projects/{project['id']}/experiments",
        headers=headers,
        json=_create_training_request(project, dataset, ["Linear Regression", "Random Forest Regressor"]),
    )
    assert created.status_code == 201, created.text
    train_candidate = trainer._train_candidate

    def fail_linear_model(db, experiment, record, *args, **kwargs):
        if record.algorithm == "Linear Regression":
            raise ValueError("simulated candidate failure")
        return train_candidate(db, experiment, record, *args, **kwargs)

    monkeypatch.setattr(trainer, "_train_candidate", fail_linear_model)
    trained = client.post(f"/api/v1/experiments/{created.json()['id']}/train", headers=headers)
    assert trained.status_code == 200, trained.text
    body = trained.json()
    assert body["status"] == "completed"
    assert {model["status"] for model in body["models"]} == {"failed", "completed"}
    assert body["best_model_id"] is not None
