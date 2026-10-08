"""
Course material service.

Handles faculty upload of academic reference materials, document processing pipeline,
vector indexing into ChromaDB, and access control.
"""

import logging
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.exceptions import (
    AppException,
    InsufficientPermissionsError,
    NotEnrolledError,
    ResourceNotFoundError,
)
from app.models.course_material import CourseMaterial, MaterialProcessingStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.course_material import ChunkSearchResult
from app.services.document_processing.chunker import chunk_text
from app.services.document_processing.docx_processor import extract_text_from_docx
from app.services.document_processing.pdf_processor import extract_text_from_pdf
from app.services.enrollment_service import is_student_enrolled
from app.services.file_storage.storage import get_file_storage_service
from app.services.rag.retriever import get_academic_retriever
from app.services.rag.vector_store import get_vector_store_service

logger = logging.getLogger(__name__)


def process_material_document(db: Session, material_id: int) -> CourseMaterial:
    """
    Execute document processing and vectorization pipeline:
      1. Extract text (PDF via PyMuPDF or DOCX via python-docx)
      2. Clean text
      3. Chunk text deterministically with metadata
      4. Embed and persist chunks into ChromaDB
      5. Update processing_status to PROCESSED (or FAILED on error)
    """
    material = db.scalar(select(CourseMaterial).where(CourseMaterial.id == material_id))
    if not material:
        raise ResourceNotFoundError(f"Course material with ID {material_id} not found.")

    material.processing_status = MaterialProcessingStatus.PROCESSING
    db.flush()

    settings = get_settings()
    vector_store = get_vector_store_service()

    try:
        file_path = Path(material.file_path)
        if not file_path.exists():
            raise AppException(f"Source file not found at {material.file_path}", status_code=404)

        # 1 & 2. Extract and clean text based on document type
        if material.file_type.lower() == "pdf":
            raw_text = extract_text_from_pdf(str(file_path))
        elif material.file_type.lower() == "docx":
            raw_text = extract_text_from_docx(str(file_path))
        else:
            raise AppException(f"Unsupported file type: {material.file_type}", status_code=422)

        if not raw_text.strip():
            logger.warning("Extracted text is empty for material ID %s", material_id)
            raw_text = f"Empty academic document: {material.title}"

        # 3. Chunk text deterministically
        chunks = chunk_text(
            text=raw_text,
            subject_id=material.subject_id,
            course_material_id=material.id,
            source_filename=material.original_filename,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        # 4. Embed and store in ChromaDB
        if chunks:
            vector_store.add_chunks(chunks)

        material.processing_status = MaterialProcessingStatus.PROCESSED
        db.flush()
        db.refresh(material)
        return material

    except Exception as exc:
        material.processing_status = MaterialProcessingStatus.FAILED
        db.flush()
        logger.error("Processing failed for material ID %s: %s", material_id, exc, exc_info=True)
        raise AppException(f"Document processing failed: {exc}", status_code=422) from exc


async def upload_course_material(
    db: Session,
    subject_id: int,
    title: str,
    file: UploadFile,
    current_faculty: User,
    auto_process: bool = True,
) -> CourseMaterial:
    """Upload academic material (PDF/DOCX) for a subject owned by current faculty."""
    if current_faculty.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    subject = db.scalar(select(Subject).where(Subject.id == subject_id))
    if not subject:
        raise ResourceNotFoundError(f"Subject with ID {subject_id} not found.")

    if subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    storage = get_file_storage_service()
    saved = await storage.save_course_material(file)

    material = CourseMaterial(
        subject_id=subject_id,
        uploaded_by=current_faculty.id,
        title=title.strip() or saved["original_filename"],
        original_filename=saved["original_filename"],
        stored_filename=saved["stored_filename"],
        file_path=saved["file_path"],
        file_type=saved["file_type"],
        file_size=saved["file_size"],
        processing_status=MaterialProcessingStatus.UPLOADED,
    )
    db.add(material)
    db.flush()
    db.refresh(material)

    if auto_process:
        try:
            process_material_document(db, material.id)
        except Exception:
            # Material record is saved with FAILED status
            pass

    db.refresh(material)
    return material


def list_subject_materials(
    db: Session, subject_id: int, current_user: User
) -> list[CourseMaterial]:
    """List course materials for a subject."""
    subject = db.scalar(select(Subject).where(Subject.id == subject_id))
    if not subject:
        raise ResourceNotFoundError(f"Subject with ID {subject_id} not found.")

    if current_user.role == UserRole.FACULTY:
        if subject.faculty_id != current_user.id:
            raise InsufficientPermissionsError()
    else:
        if not is_student_enrolled(db, current_user.id, subject_id):
            raise NotEnrolledError()

    stmt = (
        select(CourseMaterial)
        .where(CourseMaterial.subject_id == subject_id)
        .order_by(CourseMaterial.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_course_material(
    db: Session, material_id: int, current_user: User
) -> CourseMaterial:
    """Get single course material by ID."""
    stmt = (
        select(CourseMaterial)
        .options(selectinload(CourseMaterial.subject))
        .where(CourseMaterial.id == material_id)
    )
    material = db.scalar(stmt)
    if not material:
        raise ResourceNotFoundError(f"Course material with ID {material_id} not found.")

    if current_user.role == UserRole.FACULTY:
        if material.subject.faculty_id != current_user.id:
            raise InsufficientPermissionsError()
    else:
        if not is_student_enrolled(db, current_user.id, material.subject_id):
            raise NotEnrolledError()

    return material


def delete_course_material(
    db: Session, material_id: int, current_faculty: User
) -> None:
    """Delete course material, its physical file, and its vector embeddings."""
    if current_faculty.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    stmt = (
        select(CourseMaterial)
        .options(selectinload(CourseMaterial.subject))
        .where(CourseMaterial.id == material_id)
    )
    material = db.scalar(stmt)
    if not material:
        raise ResourceNotFoundError(f"Course material with ID {material_id} not found.")

    if material.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    # 1. Remove vector chunks from ChromaDB
    vector_store = get_vector_store_service()
    vector_store.delete_material_chunks(material.id)

    # 2. Delete physical file
    storage = get_file_storage_service()
    storage.delete_file(material.file_path)

    # 3. Delete database record
    db.delete(material)
    db.flush()


def search_subject_knowledge(
    db: Session,
    subject_id: int,
    query: str,
    current_user: User,
    course_material_id: int | None = None,
    top_k: int | None = None,
) -> list[ChunkSearchResult]:
    """Retrieve top-k relevant chunks from subject's course materials."""
    subject = db.scalar(select(Subject).where(Subject.id == subject_id))
    if not subject:
        raise ResourceNotFoundError(f"Subject with ID {subject_id} not found.")

    if current_user.role == UserRole.FACULTY:
        if subject.faculty_id != current_user.id:
            raise InsufficientPermissionsError()
    else:
        if not is_student_enrolled(db, current_user.id, subject_id):
            raise NotEnrolledError()

    retriever = get_academic_retriever()
    return retriever.retrieve(
        query=query,
        subject_id=subject_id,
        course_material_id=course_material_id,
        top_k=top_k,
    )
