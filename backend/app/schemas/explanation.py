from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FeatureContribution(BaseModel):
    feature: str
    contribution: float
    absolute_contribution: float
    direction: Literal["positive", "negative", "neutral"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExplanationRead(BaseModel):
    model_id: int
    experiment_id: int
    algorithm: str
    problem_type: str
    status: str = "completed"
    explanation_method: str = "shap"
    feature_importance: list[FeatureContribution] = Field(default_factory=list)
    local_explanation: list[FeatureContribution] | None = None
    base_value: float | None = None
    prediction: float | None = None
    explanation_summary: str = ""
    limitations: list[str] = Field(default_factory=list)
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)
