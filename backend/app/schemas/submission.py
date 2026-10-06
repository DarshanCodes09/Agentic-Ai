"""
Pydantic schemas for Submission resources.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.submission import SubmissionStatus
from app.schemas.user import UserBrief


class SubmissionCreate(BaseModel):
    submission_text: str | None = None


class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    submission_text: str | None = None
    file_path: str | None = None
    original_filename: str | None = None
    submitted_at: datetime
    status: SubmissionStatus
    created_at: datetime
    updated_at: datetime
    student: UserBrief | None = None

    model_config = {"from_attributes": True}
