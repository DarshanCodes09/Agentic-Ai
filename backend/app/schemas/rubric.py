"""
Pydantic schemas for Rubric and RubricItem resources.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class RubricItemCreate(BaseModel):
    criterion: str = Field(..., min_length=1, max_length=255, description="Criterion title")
    description: str | None = Field(None, description="Detailed explanation of criterion")
    max_marks: float = Field(..., gt=0, description="Criterion max marks, must be > 0")


class RubricItemUpdate(BaseModel):
    criterion: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    max_marks: float | None = Field(None, gt=0)


class RubricItemResponse(BaseModel):
    id: int
    rubric_id: int
    criterion: str
    description: str | None
    max_marks: float
    created_at: datetime

    model_config = {"from_attributes": True}


class RubricCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    items: list[RubricItemCreate] | None = None


class RubricUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class RubricResponse(BaseModel):
    id: int
    assignment_id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    items: list[RubricItemResponse] = []

    model_config = {"from_attributes": True}
