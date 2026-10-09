"""
Enrollment API routes.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_student
from app.database.session import get_db
from app.models.user import User
from app.schemas.enrollment import EnrollmentJoinRequest, EnrollmentResponse
from app.services import enrollment_service

router = APIRouter(prefix="/api/enrollments", tags=["Enrollments"])


@router.post(
    "/join",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join a course by course code (Students only)",
)
def join_course_by_code(
    payload: EnrollmentJoinRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> EnrollmentResponse:
    return enrollment_service.enroll_student_by_course_code(
        db=db,
        course_code=payload.course_code,
        student_user=current_user,
    )
