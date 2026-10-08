"""
Course Materials API routes: retrieve, delete, and process individual materials.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_faculty
from app.database.session import get_db
from app.models.user import User
from app.schemas.course_material import CourseMaterialResponse
from app.services import course_material_service

router = APIRouter(prefix="/api/materials", tags=["Course Materials"])


@router.get(
    "/{material_id}",
    response_model=CourseMaterialResponse,
    summary="Get course material by ID (Faculty owner or enrolled student)",
)
def get_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseMaterialResponse:
    return course_material_service.get_course_material(db, material_id, current_user)


@router.delete(
    "/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete course material, file, and vector embeddings (Faculty owner only)",
)
def delete_material(
    material_id: int,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> None:
    course_material_service.delete_course_material(db, material_id, current_user)


@router.post(
    "/{material_id}/process",
    response_model=CourseMaterialResponse,
    summary="Manually trigger or retry document processing & vector indexing (Faculty owner only)",
)
def process_material(
    material_id: int,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> CourseMaterialResponse:
    # Verify faculty ownership first
    material = course_material_service.get_course_material(db, material_id, current_user)
    return course_material_service.process_material_document(db, material.id)
