import os
import io
import pytest
import app.services.rag_service
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import status

from app.config.settings import settings
from app.database.connection import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.models.project import Project
from app.models.experiment import Experiment, TrainedModel
from app.models.explanation import Explanation
from app.models.dataset import Dataset
import numpy as np
import pandas as pd

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def reset_db(tmp_path, monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "DATASET_STORAGE_PATH", str(tmp_path / "datasets"))
    monkeypatch.setattr(settings, "MODEL_ARTIFACT_STORAGE_PATH", str(tmp_path / "models"))
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture
def setup_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password"},
    )
    # The register endpoint automatically logs in or we just login
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password"},
    )
    token = response.json()["access_token"]
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "test@example.com").first()
    db.close()
    return user, token

@pytest.fixture
def mock_qdrant():
    with patch("app.services.rag_service.QdrantClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance

        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_instance.get_collections.return_value = mock_collections

        yield mock_instance

@pytest.fixture
def mock_genai():
    with patch("app.services.rag_service.genai.Client") as mock_client, \
         patch("app.agents.explanation_agent.genai.Client") as mock_agent_client, \
         patch("app.api.v1.endpoints.projects.genai.Client") as mock_chat_client:

        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_agent_client.return_value = mock_instance
        mock_chat_client.return_value = mock_instance

        mock_embed_response = MagicMock()
        mock_embed = MagicMock()
        mock_embed.values = [0.1] * 768
        mock_embed_response.embeddings = [mock_embed]
        mock_instance.models.embed_content.return_value = mock_embed_response

        mock_generate_response = MagicMock()
        mock_generate_response.text = '{"natural_language_explanation": "Test explanation.", "limitations": "Test limitations."}'
        mock_instance.models.generate_content.return_value = mock_generate_response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            yield mock_instance

@pytest.fixture
def setup_experiment(db_session, setup_user):
    user, token = setup_user

    project = Project(
        user_id=user.id,
        name="Test Project",
        problem_statement="Test statement",
        objective="Test objective",
        mode="engineering",
        status="Created"
    )
    db_session.add(project)
    db_session.commit()

    dataset = Dataset(
        project_id=project.id,
        filename="test.csv",
        original_filename="test.csv",
        storage_key="fake_key",
        file_path="/fake",
        status="completed"
    )
    db_session.add(dataset)
    db_session.commit()

    experiment = Experiment(
        project_id=project.id,
        dataset_id=dataset.id,
        problem_type="regression",
        experiment_name="Test Exp",
        status="completed",
        test_size=0.2,
        configuration={"allow_identifier_target": False},
        target_column="target"
    )
    db_session.add(experiment)
    db_session.commit()

    model1 = TrainedModel(
        experiment_id=experiment.id,
        name="Test RF",
        algorithm="Random Forest Regressor",
        status="completed",
        mlflow_run_id="fake_run_id"
    )
    model2 = TrainedModel(
        experiment_id=experiment.id,
        name="Test KM",
        algorithm="K-Means",
        status="completed",
        mlflow_run_id="fake_run_id"
    )

    db_session.add(model1)
    db_session.add(model2)
    db_session.commit()

    return user, token, project, experiment, model1, model2

def test_explain_supported_model(client, db_session, setup_experiment, mock_qdrant, mock_genai):
    user, token, project, experiment, model1, model2 = setup_experiment

    with patch("mlflow.sklearn.load_model") as mock_load_model, \
         patch("app.api.v1.endpoints.experiments._load_dataset_frame") as mock_load_frame, \
         patch("app.api.v1.endpoints.experiments.validate_training_frame") as mock_validate:

        mock_validate.return_value = pd.DataFrame({"A": [1, 2], "target": [0, 1]})
        mock_load_frame.return_value = (pd.DataFrame(), None)

        with patch("app.api.v1.endpoints.experiments.explain_model") as mock_explain_model:
            mock_explain_model.return_value = {"A": 0.9}

            headers = {"Authorization": f"Bearer {token}"}
            response = client.get(f"/api/v1/experiments/{experiment.id}/models/{model1.id}/explain", headers=headers)

            assert response.status_code == 200, response.text
            data = response.json()
            assert data["method"] == "shap"
            assert data["importances"] == {"A": 0.9}
            assert "Test explanation" in data["natural_language_explanation"]

            explanation = db_session.query(Explanation).filter(Explanation.model_id == model1.id).first()
            assert explanation is not None
            assert explanation.method == "shap"

            mock_explain_model.reset_mock()
            response2 = client.get(f"/api/v1/experiments/{experiment.id}/models/{model1.id}/explain", headers=headers)
            assert response2.status_code == 200
            mock_explain_model.assert_not_called()

def test_explain_unsupported_model(client, db_session, setup_experiment, mock_qdrant, mock_genai):
    user, token, project, experiment, model1, model2 = setup_experiment

    with patch("mlflow.sklearn.load_model"), \
         patch("app.api.v1.endpoints.experiments._load_dataset_frame") as mock_load_frame, \
         patch("app.api.v1.endpoints.experiments.validate_training_frame") as mock_validate:

        mock_validate.return_value = pd.DataFrame({"A": [1, 2], "target": [0, 1]})
        mock_load_frame.return_value = (pd.DataFrame(), None)

        with patch("app.api.v1.endpoints.experiments.explain_model") as mock_explain_model:
            mock_explain_model.return_value = {"error": "unsupported", "message": "Unsupported."}

            headers = {"Authorization": f"Bearer {token}"}
            response = client.get(f"/api/v1/experiments/{experiment.id}/models/{model2.id}/explain", headers=headers)

            assert response.status_code == 200
            data = response.json()
            assert data["method"] == "none"
            assert data["importances"] is None
            assert data["status"] == "unsupported"
            assert "Test explanation" in data["natural_language_explanation"]

def test_explain_ownership(client, db_session, setup_experiment):
    _, _, _, experiment, model1, _ = setup_experiment

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "password"},
    )
    other_token = response.json()["access_token"]

    headers = {"Authorization": f"Bearer {other_token}"}
    response = client.get(f"/api/v1/experiments/{experiment.id}/models/{model1.id}/explain", headers=headers)
    assert response.status_code == 404

def test_project_chat_learning_mode_only(client, db_session, setup_experiment):
    user, token, project, experiment, _, _ = setup_experiment

    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(f"/api/v1/projects/{project.id}/chat", headers=headers, json={"message": "hello"})
    assert response.status_code == 400
    assert "learning mode" in response.json()["detail"].lower()

def test_project_chat_rag_retrieval(client, db_session, setup_experiment, mock_qdrant, mock_genai):
    user, token, project, experiment, _, _ = setup_experiment

    project.mode = "learning"
    db_session.commit()

    mock_hit = MagicMock()
    mock_hit.payload = {"title": "Test Doc", "text": "This is a retrieved RAG document."}
    mock_qdrant.search.return_value = [mock_hit]

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}):
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(f"/api/v1/projects/{project.id}/chat", headers=headers, json={"message": "hello"})

        assert response.status_code == 200
        mock_qdrant.search.assert_called_once()

        call_args = mock_genai.models.generate_content.call_args
        prompt = call_args[1]["contents"]
        assert "This is a retrieved RAG document" in prompt


def test_canonical_model_explain_route(client, db_session, setup_experiment):
    _, token, _, _, model1, _ = setup_experiment
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.explainability_service.ExplainabilityService.build_response") as mock_response:
        mock_response.return_value = {
            "model_id": model1.id,
            "experiment_id": model1.experiment_id,
            "algorithm": model1.algorithm,
            "problem_type": "regression",
            "status": "completed",
            "explanation_method": "shap",
            "feature_importance": [{
                "feature": "salary",
                "contribution": 0.82,
                "absolute_contribution": 0.82,
                "direction": "positive",
                "metadata": {"source": "shap"},
            }],
            "local_explanation": [{
                "feature": "salary",
                "contribution": 0.82,
                "absolute_contribution": 0.82,
                "direction": "positive",
                "metadata": {"source": "shap"},
            }],
            "base_value": 0.4,
            "prediction": 0.9,
            "explanation_summary": "Salary had the strongest influence on this prediction.",
            "limitations": ["Influence is not causation."],
            "generated_at": "2026-10-07T00:00:00+00:00",
        }

        response = client.get(f"/api/v1/models/{model1.id}/explain", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["algorithm"] == model1.algorithm
        assert data["feature_importance"][0]["feature"] == "salary"
        assert data["explanation_summary"].startswith("Salary")
