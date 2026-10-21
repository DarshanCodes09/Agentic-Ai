"""
Pydantic schemas for Rubric and RubricItem resources.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RubricItemCreate(BaseModel):
    criterion: str = Field(..., min_length=1, max_length=255, description="Criterion title")
    description: str | None = Field(None, description="Detailed explanation of criterion")
    max_marks: float = Field(..., gt=0, description="Criterion max marks, must be > 0")

    @field_validator("criterion")
    @classmethod
    def validate_criterion(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Criterion title cannot be empty or blank")
        return s


class RubricItemUpdate(BaseModel):
    criterion: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    max_marks: float | None = Field(None, gt=0)

    @field_validator("criterion")
    @classmethod
    def validate_criterion(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Criterion title cannot be empty or blank")
            return s
        return v


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

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Rubric name cannot be empty or blank")
        return s

    @field_validator("items")
    @classmethod
    def validate_items(cls, items: list[RubricItemCreate] | None) -> list[RubricItemCreate] | None:
        if items is not None:
            seen = set()
            for item in items:
                norm = item.criterion.strip().lower()
                if norm in seen:
                    raise ValueError(f"Duplicate rubric criterion '{item.criterion.strip()}' found")
                seen.add(norm)
        return items


class RubricUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Rubric name cannot be empty or blank")
            return s
        return v


class RubricResponse(BaseModel):
    id: int
    assignment_id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    items: list[RubricItemResponse] = []

    model_config = {"from_attributes": True}
