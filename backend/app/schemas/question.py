"""
Pydantic schemas for Question resources.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    question_number: int = Field(..., ge=1, description="Question sequence number, unique per assignment")
    question_text: str = Field(..., min_length=1, description="The assignment question prompt")
    marks: float = Field(..., gt=0, description="Marks assigned to question, must be > 0")
    expected_concepts: list[str] | None = Field(
        default=None,
        description="Key conceptual keywords or learning points expected in the answer",
    )


class QuestionUpdate(BaseModel):
    question_number: int | None = Field(None, ge=1)
    question_text: str | None = Field(None, min_length=1)
    marks: float | None = Field(None, gt=0)
    expected_concepts: list[str] | None = None


class QuestionResponse(BaseModel):
    id: int
    assignment_id: int
    question_number: int
    question_text: str
    marks: float
    expected_concepts: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
