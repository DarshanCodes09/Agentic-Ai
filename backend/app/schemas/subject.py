"""
Pydantic schemas for Subject resources.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserBrief


class SubjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Subject name")
    code: str = Field(..., min_length=1, max_length=50, description="Unique subject code, e.g. CS101")
    description: str | None = Field(None, description="Detailed subject overview")


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class SubjectResponse(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    faculty_id: int
    faculty: UserBrief | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
