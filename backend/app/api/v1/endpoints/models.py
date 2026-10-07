from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.database.connection import get_db
from app.models.experiment import TrainedModel
from app.models.user import User
from app.schemas.explanation import ExplanationRead
from app.services.explainability_service import ExplainabilityService

router = APIRouter()


@router.get("/{model_id}/explain", response_model=ExplanationRead)
def explain_model_by_id(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ExplainabilityService(db)
    try:
        model = service.get_owned_model(model_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found.") from exc

    if model.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only successfully trained models can be explained.",
        )

    payload = service.build_response(model)
    return {
        "model_id": payload["model_id"],
        "experiment_id": payload["experiment_id"],
        "algorithm": payload["algorithm"],
        "problem_type": payload["problem_type"],
        "status": payload["status"],
        "explanation_method": payload["explanation_method"],
        "feature_importance": payload["feature_importance"],
        "local_explanation": payload.get("local_explanation"),
        "base_value": payload.get("base_value"),
        "prediction": payload.get("prediction"),
        "explanation_summary": payload["explanation_summary"],
        "limitations": payload["limitations"],
        "generated_at": payload["generated_at"],
    }
