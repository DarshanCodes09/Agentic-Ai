"""
Pydantic schemas for Enrollment resources.
"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.user import UserBrief


class EnrollmentCreate(BaseModel):
    subject_id: int | None = None


class EnrollmentJoinRequest(BaseModel):
    course_code: str


class EnrollmentResponse(BaseModel):
    id: int
    student_id: int
    subject_id: int
    enrolled_at: datetime
    student: UserBrief | None = None

    model_config = {"from_attributes": True}
