"""
Pydantic schemas for Assignment resources.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.rubric import RubricCreate, RubricResponse


class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    instructions: str | None = None
    due_date: datetime
    max_marks: float = Field(..., gt=0, description="Total possible marks, must be > 0")
    rubric: RubricCreate | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Assignment title cannot be empty or blank")
        return s

    @model_validator(mode="after")
    def validate_rubric_marks(self) -> "AssignmentCreate":
        if self.rubric and self.rubric.items:
            criteria_sum = sum(item.max_marks for item in self.rubric.items)
            if criteria_sum > self.max_marks:
                raise ValueError(
                    f"Total rubric criteria marks ({criteria_sum}) cannot exceed assignment maximum marks ({self.max_marks})."
                )
        return self


class AssignmentUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    instructions: str | None = None
    due_date: datetime | None = None
    max_marks: float | None = Field(None, gt=0)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Assignment title cannot be empty or blank")
            return s
        return v


class AssignmentResponse(BaseModel):
    id: int
    subject_id: int
    title: str
    description: str | None
    instructions: str | None
    due_date: datetime
    max_marks: float
    created_by: int
    created_at: datetime
    updated_at: datetime
    rubric: RubricResponse | None = None

    model_config = {"from_attributes": True}
