from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ProblemType = Literal["regression", "classification", "clustering"]


class ExperimentCreate(BaseModel):
    dataset_id: int = Field(gt=0)
    problem_type: ProblemType
    target_column: Optional[str] = Field(default=None, max_length=255)
    target_confirmed: bool = False
    allow_identifier_target: bool = False
    selected_algorithms: list[str] = Field(min_length=1, max_length=3)
    test_size: float = Field(default=0.2, ge=0.1, le=0.4)
    random_state: int = Field(default=42, ge=0, le=2_147_483_647)
    optimize: bool = False

    @field_validator("target_column")
    @classmethod
    def normalize_target_column(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value and value.strip() else None

    @field_validator("selected_algorithms")
    @classmethod
    def validate_selected_algorithms(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("Algorithm names cannot be empty.")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Algorithms must be unique.")
        return normalized

    @model_validator(mode="after")
    def validate_target_confirmation(self):
        if self.problem_type == "clustering":
            if self.target_column is not None:
                raise ValueError("Clustering does not accept a target column.")
            return self

        if not self.target_column:
            raise ValueError("Select a target column before creating an experiment.")
        if not self.target_confirmed:
            raise ValueError("Confirm the target column before creating an experiment.")
        return self


class TrainedModelRead(BaseModel):
    id: int
    experiment_id: int
    name: str
    algorithm: str
    status: str
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    preprocessing: dict[str, Any]
    mlflow_run_id: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExperimentRead(BaseModel):
    id: int
    project_id: int
    dataset_id: Optional[int]
    problem_type: str
    target_column: Optional[str]
    experiment_name: str
    status: str
    random_state: int
    test_size: float
    configuration: dict[str, Any]
    best_model_id: Optional[int]
    comparison_policy: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    models: list[TrainedModelRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ExperimentComparisonRead(BaseModel):
    experiment_id: int
    status: str
    problem_type: str
    comparison_policy: Optional[str]
    best_model_id: Optional[int]
    candidates: list[TrainedModelRead]
