from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class RecommendationResponse(BaseModel):
    project_id: Optional[int] = None
    dataset_id: Optional[int] = None
    project_name: Optional[str] = None
    problem_statement: str = ""
    objective: str = ""
    problem_type: str = "unknown"
    target_candidate: Optional[str] = None
    feature_candidates: List[str] = Field(default_factory=list)
    dataset_summary: Dict[str, Any] = Field(default_factory=dict)
    dataset_characteristics: Dict[str, Any] = Field(default_factory=dict)
    recommended_pipeline: str = ""
    candidate_algorithms: List[str] = Field(default_factory=list)
    preprocessing_steps: List[str] = Field(default_factory=list)
    rationale: str = ""
    confidence: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    explanation: str = ""
    errors: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")
