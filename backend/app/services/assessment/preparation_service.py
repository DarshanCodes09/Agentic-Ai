"""
Assessment context preparation service.
Extracts submission content, structures rubric criteria, and retrieves relevant course knowledge.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppException, ResourceNotFoundError
from app.models.assignment import Assignment
from app.models.question import Question
from app.models.rubric import Rubric
from app.models.submission import Submission
from app.services.document_processing.docx_processor import extract_text_from_docx
from app.services.document_processing.pdf_processor import extract_text_from_pdf
from app.services.rag.retriever import get_academic_retriever

logger = logging.getLogger(__name__)


@dataclass
class AssessmentContext:
    """Pre-assembled context ready for AssessmentAgent & FeedbackAgent evaluation."""
    submission: Submission
    assignment_title: str
    assignment_description: str | None
    total_max_marks: float
    questions: list[dict[str, Any]] = field(default_factory=list)
    rubric_items: list[dict[str, Any]] = field(default_factory=list)
    submission_text: str = ""
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    knowledge_context_available: bool = False


class AssessmentPreparationService:
    """Assembles all data required to assess a student submission."""

    def prepare_context(self, db: Session, submission_id: int) -> AssessmentContext:
        """
        Fetch submission, extract student answer, format rubric & questions,
        and retrieve academic course chunks.
        """
        stmt = (
            select(Submission)
            .options(
                selectinload(Submission.assignment).selectinload(Assignment.subject),
                selectinload(Submission.assignment).selectinload(Assignment.questions),
                selectinload(Submission.assignment).selectinload(Assignment.rubric).selectinload(Rubric.items),
            )
            .where(Submission.id == submission_id)
        )
        submission = db.scalar(stmt)
        if not submission:
            raise ResourceNotFoundError(f"Submission with ID {submission_id} not found.")

        assignment = submission.assignment
        if not assignment:
            raise ResourceNotFoundError(f"Assignment for submission {submission_id} not found.")

        # 1. Resolve student submission text
        submission_text = self._resolve_submission_text(submission)
        if not submission_text.strip():
            raise AppException(
                detail="Submission content is empty or could not be extracted.",
                status_code=422,
            )

        # 2. Extract Questions and Expected Concepts
        questions_data: list[dict[str, Any]] = []
        total_q_marks = 0.0
        query_terms: list[str] = [assignment.title]

        for q in sorted(assignment.questions, key=lambda x: x.question_number):
            q_marks = float(q.marks)
            total_q_marks += q_marks
            concepts = q.expected_concepts if isinstance(q.expected_concepts, list) else []
            questions_data.append({
                "id": q.id,
                "question_number": q.question_number,
                "question_text": q.question_text,
                "marks": q_marks,
                "expected_concepts": concepts,
            })
            query_terms.append(q.question_text)
            for c in concepts:
                if isinstance(c, str):
                    query_terms.append(c)

        # 3. Extract Rubric Items
        rubric_items_data: list[dict[str, Any]] = []
        total_rubric_marks = 0.0
        if assignment.rubric and assignment.rubric.items:
            for item in assignment.rubric.items:
                m_marks = float(item.max_marks)
                total_rubric_marks += m_marks
                rubric_items_data.append({
                    "id": item.id,
                    "criterion": item.criterion,
                    "description": item.description,
                    "max_marks": m_marks,
                })

        # Determine total max marks
        if total_q_marks > 0:
            total_max_marks = total_q_marks
        elif total_rubric_marks > 0:
            total_max_marks = total_rubric_marks
        else:
            total_max_marks = 100.0

        # If no rubric items exist, create a default criterion using total marks
        if not rubric_items_data:
            rubric_items_data.append({
                "id": None,
                "criterion": "Comprehensive Technical & Academic Accuracy",
                "description": "General adherence to the assignment questions and disciplinary standards.",
                "max_marks": total_max_marks,
            })

        # 4. RAG Retrieval from Course Materials
        retrieved_chunks = self._retrieve_rag_context(
            subject_id=assignment.subject_id,
            query_terms=query_terms,
        )

        return AssessmentContext(
            submission=submission,
            assignment_title=assignment.title,
            assignment_description=assignment.description,
            total_max_marks=total_max_marks,
            questions=questions_data,
            rubric_items=rubric_items_data,
            submission_text=submission_text,
            retrieved_chunks=retrieved_chunks,
            knowledge_context_available=len(retrieved_chunks) > 0,
        )

    def _resolve_submission_text(self, submission: Submission) -> str:
        """Extract text from submission_text or uploaded file if present."""
        text_parts: list[str] = []
        if submission.submission_text and submission.submission_text.strip():
            text_parts.append(submission.submission_text.strip())

        if submission.file_path:
            file_p = Path(submission.file_path)
            if file_p.exists():
                try:
                    ext = file_p.suffix.lower()
                    if ext == ".pdf":
                        extracted = extract_text_from_pdf(file_p)
                        if extracted:
                            text_parts.append(extracted)
                    elif ext in [".docx", ".doc"]:
                        extracted = extract_text_from_docx(file_p)
                        if extracted:
                            text_parts.append(extracted)
                except Exception as exc:
                    logger.warning("Could not extract text from submission file %s: %s", file_p, exc)

        return "\n\n".join(text_parts).strip()

    def _retrieve_rag_context(
        self, subject_id: int, query_terms: list[str], top_k: int = 4
    ) -> list[dict[str, Any]]:
        """Retrieve relevant course material knowledge via AcademicRetriever."""
        try:
            retriever = get_academic_retriever()
            query = " ".join(query_terms)[:500]
            chunks = retriever.retrieve(
                query=query,
                subject_id=subject_id,
                top_k=top_k,
            )
            return [
                {
                    "chunk_text": c.chunk_text,
                    "similarity": c.similarity,
                    "metadata": c.metadata.model_dump() if hasattr(c.metadata, "model_dump") else c.metadata,
                }
                for c in chunks
            ]
        except Exception as exc:
            logger.warning("RAG retrieval failed or vector store not initialized: %s", exc)
            return []


_prep_service_instance: AssessmentPreparationService | None = None


def get_assessment_preparation_service() -> AssessmentPreparationService:
    global _prep_service_instance
    if _prep_service_instance is None:
        _prep_service_instance = AssessmentPreparationService()
    return _prep_service_instance
