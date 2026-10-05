from typing import Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    project_id: int
    project_name: str
    problem_statement: str
    objective: str
    dataset_id: int
    dataset_summary: Dict[str, Any]
    problem_type: str
    target_candidate: Optional[str]
    feature_candidates: List[str]
    dataset_characteristics: Dict[str, Any]
    recommended_pipeline: str
    candidate_algorithms: List[str]
    preprocessing_steps: List[str]
    rationale: str
    confidence: float
    warnings: List[str]
    explanation: str
    errors: List[str]
