"""
Subject & Enrollment API routes.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_faculty, require_student
from app.core.exceptions import InsufficientPermissionsError, NotEnrolledError
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.assignment import AssignmentCreate, AssignmentResponse
from app.schemas.course_material import (
    ChunkSearchResult,
    CourseMaterialResponse,
    MaterialSearchQuery,
)
from app.schemas.enrollment import EnrollmentResponse
from app.schemas.subject import SubjectCreate, SubjectResponse, SubjectUpdate
from app.services import (
    assignment_service,
    course_material_service,
    enrollment_service,
    subject_service,
)

router = APIRouter(prefix="/api/subjects", tags=["Subjects"])


@router.post(
    "",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new subject (Faculty only)",
)
def create_subject(
    payload: SubjectCreate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> SubjectResponse:
    return subject_service.create_subject(db, payload, current_user)


@router.get(
    "",
    response_model=list[SubjectResponse],
    summary="List subjects (Faculty: own subjects; Students: enrolled subjects)",
)
def list_subjects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SubjectResponse]:
    if current_user.role == UserRole.FACULTY:
        return subject_service.list_faculty_subjects(db, current_user.id)
    return subject_service.list_student_subjects(db, current_user.id)


@router.get(
    "/available",
    response_model=list[SubjectResponse],
    summary="List subjects available to join (Students only)",
)
def list_available_subjects(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[SubjectResponse]:
    return subject_service.list_available_subjects_for_student(db, current_user.id)


@router.get(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Get subject by ID (Faculty own / Student enrolled)",
)
def get_subject(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubjectResponse:
    subject = subject_service.get_subject_by_id(db, subject_id)
    if current_user.role == UserRole.FACULTY:
        if subject.faculty_id != current_user.id:
            raise InsufficientPermissionsError()
    else:
        if not enrollment_service.is_student_enrolled(db, current_user.id, subject_id):
            raise NotEnrolledError()
    return subject


@router.put(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Update subject (Faculty owner only)",
)
def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> SubjectResponse:
    return subject_service.update_subject(db, subject_id, payload, current_user)


@router.delete(
    "/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete subject (Faculty owner only)",
)
def delete_subject(
    subject_id: int,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> None:
    subject_service.delete_subject(db, subject_id, current_user)


# ---------------------------------------------------------------------------
# Enrollment Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{subject_id}/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll in a subject (Students only)",
)
def enroll_in_subject(
    subject_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> EnrollmentResponse:
    return enrollment_service.enroll_student(db, subject_id, current_user)


@router.get(
    "/{subject_id}/students",
    response_model=list[EnrollmentResponse],
    summary="List enrolled students (Faculty owner only)",
)
def get_enrolled_students(
    subject_id: int,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> list[EnrollmentResponse]:
    return enrollment_service.get_subject_students(db, subject_id, current_user)


# ---------------------------------------------------------------------------
# Subject Assignments
# ---------------------------------------------------------------------------

@router.post(
    "/{subject_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create assignment for subject (Faculty owner only)",
)
def create_subject_assignment(
    subject_id: int,
    payload: AssignmentCreate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return assignment_service.create_assignment(db, subject_id, payload, current_user)


@router.get(
    "/{subject_id}/assignments",
    response_model=list[AssignmentResponse],
    summary="List assignments for subject (Faculty owner or enrolled student)",
)
def list_subject_assignments(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AssignmentResponse]:
    return assignment_service.list_subject_assignments(db, subject_id, current_user)


# ---------------------------------------------------------------------------
# Subject Course Materials (Phase 3)
# ---------------------------------------------------------------------------

@router.post(
    "/{subject_id}/materials",
    response_model=CourseMaterialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload course material PDF/DOCX (Faculty owner only)",
)
async def upload_material(
    subject_id: int,
    file: UploadFile = File(...),
    title: str = Form(""),
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> CourseMaterialResponse:
    return await course_material_service.upload_course_material(
        db, subject_id, title, file, current_user
    )


@router.get(
    "/{subject_id}/materials",
    response_model=list[CourseMaterialResponse],
    summary="List course materials (Faculty owner or enrolled student)",
)
def list_materials(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CourseMaterialResponse]:
    return course_material_service.list_subject_materials(db, subject_id, current_user)


@router.post(
    "/{subject_id}/materials/search",
    response_model=list[ChunkSearchResult],
    summary="Semantic retrieval search over subject course materials",
)
def search_materials(
    subject_id: int,
    query: MaterialSearchQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChunkSearchResult]:
    return course_material_service.search_subject_knowledge(
        db,
        subject_id=subject_id,
        query=query.query,
        current_user=current_user,
        course_material_id=query.course_material_id,
        top_k=query.top_k,
    )

