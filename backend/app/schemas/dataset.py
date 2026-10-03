from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DatasetSummary(BaseModel):
    row_count: int = 0
    column_count: int = 0
    columns: List[str] = Field(default_factory=list)
    missing_values: Dict[str, int] = Field(default_factory=dict)
    missing_percentages: Dict[str, float] = Field(default_factory=dict)
    duplicate_rows: int = 0
    duplicate_percentage: float = 0.0
    unique_value_counts: Dict[str, int] = Field(default_factory=dict)
    numeric_columns: List[str] = Field(default_factory=list)
    categorical_columns: List[str] = Field(default_factory=list)
    inferred_types: Dict[str, str] = Field(default_factory=dict)
    quality_score: int = 0
    quality_status: str = "failed"
    findings: List[Dict[str, Any]] = Field(default_factory=list)


class DatasetRead(BaseModel):
    id: int
    project_id: int
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    row_count: int
    column_count: int
    status: str
    uploaded_at: datetime
    updated_at: datetime
    summary: Optional[DatasetSummary] = None

    model_config = ConfigDict(from_attributes=True)


class DatasetDetail(DatasetRead):
    pass
