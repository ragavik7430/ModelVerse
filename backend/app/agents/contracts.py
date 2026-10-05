from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProblemAnalysisResult(BaseModel):
    problem_type: str = "unknown"
    target_candidate: Optional[str] = None
    confidence: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    rationale: str = ""


class DatasetCharacteristics(BaseModel):
    row_count: int = 0
    column_count: int = 0
    numeric_columns: List[str] = Field(default_factory=list)
    categorical_columns: List[str] = Field(default_factory=list)
    missing_values: Dict[str, int] = Field(default_factory=dict)
    duplicate_rows: int = 0
    quality_score: int = 0
    quality_status: str = "unknown"
    findings: List[Dict[str, Any]] = Field(default_factory=list)


class RecommendationResult(BaseModel):
    project_id: Optional[int] = None
    dataset_id: Optional[int] = None
    problem_type: str = "unknown"
    target_candidate: Optional[str] = None
    problem_statement: str = ""
    objective: str = ""
    dataset_summary: Dict[str, Any] = Field(default_factory=dict)
    dataset_characteristics: Dict[str, Any] = Field(default_factory=dict)
    feature_candidates: List[str] = Field(default_factory=list)
    recommended_pipeline: str = ""
    candidate_algorithms: List[str] = Field(default_factory=list)
    preprocessing_steps: List[str] = Field(default_factory=list)
    rationale: str = ""
    confidence: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    explanation: str = ""
    errors: List[str] = Field(default_factory=list)
