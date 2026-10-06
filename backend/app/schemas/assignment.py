"""
Pydantic schemas for Assignment resources.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    instructions: str | None = None
    due_date: datetime
    max_marks: float = Field(..., gt=0, description="Total possible marks, must be > 0")


class AssignmentUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    instructions: str | None = None
    due_date: datetime | None = None
    max_marks: float | None = Field(None, gt=0)


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

    model_config = {"from_attributes": True}
