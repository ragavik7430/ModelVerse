from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, validator

ProjectMode = Literal["engineering", "learning"]


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    problem_statement: str = Field(..., min_length=1, max_length=2000)
    objective: str = Field(..., min_length=1, max_length=1000)
    mode: ProjectMode = "engineering"

    @validator("name", "problem_statement", "objective")
    def strip_and_validate_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be blank")
        return cleaned


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    problem_statement: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    objective: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    mode: Optional[ProjectMode] = None
    status: Optional[str] = Field(default=None, min_length=1, max_length=32)

    @validator("name", "problem_statement", "objective", "status")
    def strip_and_validate_optional_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be blank")
        return cleaned


class ProjectRead(BaseModel):
    id: int
    user_id: int
    name: str
    problem_statement: str
    objective: str
    mode: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
