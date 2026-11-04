"""
Assignment file service.

Manages faculty-uploaded assignment instruction and rubric documents (PDF, DOCX, TXT, MD),
enforces subject ownership and enrollment permissions, and provides secure file downloads/previews.
"""

import logging
from pathlib import Path
from fastapi import UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    AppException,
    InsufficientPermissionsError,
    NotEnrolledError,
    ResourceNotFoundError,
)
from app.models.assignment import Assignment
from app.models.assignment_file import AssignmentFile
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.services.enrollment_service import is_student_enrolled
from app.services.file_storage.security import (
    build_secure_file_response,
    validate_file_path_safe,
)
from app.services.file_storage.storage import get_file_storage_service
from app.services.rubric_extraction_service import get_rubric_extraction_service

logger = logging.getLogger(__name__)


def _get_assignment_with_subject(db: Session, assignment_id: int) -> Assignment:
    stmt = (
        select(Assignment)
        .options(selectinload(Assignment.subject), selectinload(Assignment.files))
        .where(Assignment.id == assignment_id)
    )
    assignment = db.scalar(stmt)
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")
    return assignment


def verify_assignment_access(assignment: Assignment, user: User, db: Session) -> None:
    """Verify user is either the faculty owner of the subject or an enrolled student."""
    if user.role == UserRole.FACULTY:
        if assignment.subject.faculty_id != user.id:
            raise InsufficientPermissionsError()
    elif user.role == UserRole.STUDENT:
        if not is_student_enrolled(db, user.id, assignment.subject_id):
            raise NotEnrolledError()
    else:
        raise InsufficientPermissionsError()


def verify_faculty_assignment_ownership(assignment: Assignment, faculty: User) -> None:
    """Verify faculty owns the subject associated with the assignment."""
    if faculty.role != UserRole.FACULTY or assignment.subject.faculty_id != faculty.id:
        raise InsufficientPermissionsError()


async def upload_assignment_file(
    db: Session,
    assignment_id: int,
    file: UploadFile,
    current_faculty: User,
) -> AssignmentFile:
    """
    Save an uploaded instruction/rubric file for an assignment, extract its text,
    and persist metadata.
    """
    assignment = _get_assignment_with_subject(db, assignment_id)
    verify_faculty_assignment_ownership(assignment, current_faculty)

    storage = get_file_storage_service()
    file_info = await storage.save_assignment_file(file)

    # Extract text from the saved file for search and AI evaluation
    extracted_text: str | None = None
    try:
        extractor = get_rubric_extraction_service()
        extracted_text = extractor.extract_text_from_path(file_info["file_path"])
    except Exception as exc:
        logger.warning(
            "Could not pre-extract text from assignment file %s: %s",
            file_info["original_filename"],
            exc,
        )

    assignment_file = AssignmentFile(
        assignment_id=assignment.id,
        uploaded_by=current_faculty.id,
        original_filename=file_info["original_filename"],
        stored_filename=file_info["stored_filename"],
        file_path=file_info["file_path"],
        file_type=file_info["file_type"],
        file_size=file_info["file_size"],
        extracted_text=extracted_text,
    )
    db.add(assignment_file)
    db.commit()
    db.refresh(assignment_file)
    return assignment_file


def list_assignment_files(
    db: Session,
    assignment_id: int,
    current_user: User,
) -> list[AssignmentFile]:
    """List all instruction and reference files attached to an assignment."""
    assignment = _get_assignment_with_subject(db, assignment_id)
    verify_assignment_access(assignment, current_user, db)

    stmt = (
        select(AssignmentFile)
        .where(AssignmentFile.assignment_id == assignment_id)
        .order_by(AssignmentFile.id)
    )
    return list(db.scalars(stmt).all())


def get_assignment_file(
    db: Session,
    assignment_id: int,
    file_id: int,
    current_user: User,
) -> AssignmentFile:
    """Get metadata for a specific assignment file."""
    assignment = _get_assignment_with_subject(db, assignment_id)
    verify_assignment_access(assignment, current_user, db)

    stmt = select(AssignmentFile).where(
        AssignmentFile.id == file_id,
        AssignmentFile.assignment_id == assignment_id,
    )
    assignment_file = db.scalar(stmt)
    if not assignment_file:
        raise ResourceNotFoundError(f"Assignment file with ID {file_id} not found.")
    return assignment_file


def get_assignment_file_response(
    db: Session,
    assignment_id: int,
    file_id: int,
    current_user: User,
    inline: bool = False,
) -> FileResponse:
    """
    Stream secure file download or inline preview for an assignment file with path validation.
    """
    assignment = _get_assignment_with_subject(db, assignment_id)
    verify_assignment_access(assignment, current_user, db)

    stmt = select(AssignmentFile).where(
        AssignmentFile.id == file_id,
        AssignmentFile.assignment_id == assignment_id,
    )
    assignment_file = db.scalar(stmt)
    if not assignment_file:
        raise ResourceNotFoundError(f"Assignment file with ID {file_id} not found.")

    storage = get_file_storage_service()
    safe_path = validate_file_path_safe(assignment_file.file_path, storage.assignments_dir)

    return build_secure_file_response(
        file_path=safe_path,
        original_filename=assignment_file.original_filename,
        inline=inline,
    )


def delete_assignment_file(
    db: Session,
    assignment_id: int,
    file_id: int,
    current_faculty: User,
) -> None:
    """Delete an assignment file from disk and database (faculty owner only)."""
    assignment = _get_assignment_with_subject(db, assignment_id)
    verify_faculty_assignment_ownership(assignment, current_faculty)

    stmt = select(AssignmentFile).where(
        AssignmentFile.id == file_id,
        AssignmentFile.assignment_id == assignment_id,
    )
    assignment_file = db.scalar(stmt)
    if not assignment_file:
        raise ResourceNotFoundError(f"Assignment file with ID {file_id} not found.")

    storage = get_file_storage_service()
    storage.delete_file(assignment_file.file_path)

    db.delete(assignment_file)
    db.commit()
