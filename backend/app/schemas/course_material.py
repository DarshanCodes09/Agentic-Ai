"""
Pydantic schemas for CourseMaterial resources and RAG retrieval.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.course_material import MaterialProcessingStatus


class CourseMaterialResponse(BaseModel):
    id: int
    subject_id: int
    uploaded_by: int
    title: str
    original_filename: str
    stored_filename: str
    file_type: str
    file_size: int
    processing_status: MaterialProcessingStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialSearchQuery(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    subject_id: int | None = Field(None, description="Optional subject ID filter")
    course_material_id: int | None = Field(None, description="Optional material ID filter")
    top_k: int | None = Field(None, ge=1, le=50, description="Number of results to retrieve")


class ChunkSearchResult(BaseModel):
    chunk_text: str
    similarity: float | None = None
    metadata: dict[str, Any]
