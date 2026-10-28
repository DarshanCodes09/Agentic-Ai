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

from app.core.config import get_settings
from app.core.exceptions import AppException, ResourceNotFoundError
from app.models.assignment import Assignment
from app.models.question import Question
from app.models.rubric import Rubric
from app.models.submission import Submission
from app.services.document_processing.docx_processor import extract_text_from_docx
from app.services.document_processing.notebook_processor import get_notebook_processor
from app.services.document_processing.pdf_processor import extract_text_from_pdf
from app.services.document_processing.zip_processor import get_zip_processor
from app.services.file_storage.storage import get_archive_unpacked_dir
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
    file_format: str | None = None
    file_manifest: dict[str, Any] | None = None
    execution_audit: dict[str, Any] | None = None
    assignment_instructions: str | None = None
    assignment_documents_text: str = ""
    zip_inventory: Any | None = None
    original_archive_name: str | None = None


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
                selectinload(Submission.assignment).selectinload(Assignment.files),
            )
            .where(Submission.id == submission_id)
        )
        submission = db.scalar(stmt)
        if not submission:
            raise ResourceNotFoundError(f"Submission with ID {submission_id} not found.")

        assignment = submission.assignment
        if not assignment:
            raise ResourceNotFoundError(f"Assignment for submission {submission_id} not found.")

        # 1. Extract Questions and Expected Concepts
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

        # 2. Extract Rubric Items
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
        if assignment.max_marks and float(assignment.max_marks) > 0:
            total_max_marks = float(assignment.max_marks)
        elif total_q_marks > 0:
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

        # 3. Clean assignment instructions and description
        settings = get_settings()
        clean_description = assignment.description
        if clean_description and len(clean_description) > settings.max_assignment_instructions_chars:
            clean_description = (
                clean_description[: settings.max_assignment_instructions_chars]
                + f"\n... [Assignment instructions truncated at {settings.max_assignment_instructions_chars} chars] ..."
            )

        clean_instructions = assignment.instructions
        if clean_instructions and len(clean_instructions) > settings.max_assignment_instructions_chars:
            clean_instructions = (
                clean_instructions[: settings.max_assignment_instructions_chars]
                + f"\n... [Assignment instructions truncated at {settings.max_assignment_instructions_chars} chars] ..."
            )

        # 4. Resolve student submission text, file format, and execution metadata dynamically
        submission_text, file_format, file_manifest, execution_audit, zip_inventory, original_archive_name = self._resolve_submission_payload(
            submission=submission,
            rubric_items=rubric_items_data,
            assignment_instructions=clean_instructions or clean_description,
            assignment_title=assignment.title,
        )
        if not submission_text.strip():
            raise AppException(
                detail="Submission content is empty or could not be extracted.",
                status_code=422,
            )

        # 5. Resolve attached assignment documents & specifications
        doc_parts: list[str] = []
        if assignment.files:
            from app.services.rubric_extraction_service import get_rubric_extraction_service
            for af in assignment.files:
                f_text = af.extracted_text
                if not f_text and af.file_path:
                    try:
                        extractor = get_rubric_extraction_service()
                        f_text = extractor.extract_text_from_path(af.file_path)
                        af.extracted_text = f_text
                        db.add(af)
                    except Exception as exc:
                        logger.warning("Could not extract text from assignment file %s: %s", af.original_filename, exc)
                if f_text and f_text.strip():
                    capped_text = f_text.strip()
                    max_chars_per_doc = 3000
                    if len(capped_text) > max_chars_per_doc:
                        capped_text = capped_text[:max_chars_per_doc] + f"\n... [Attached specification {af.original_filename} truncated at {max_chars_per_doc} chars] ..."
                    doc_parts.append(f"=== ATTACHED SPECIFICATION: {af.original_filename} ===\n{capped_text}")
                    query_terms.append(af.original_filename)
                    query_terms.append(capped_text[:200])

        assignment_documents_text = "\n\n".join(doc_parts)

        # 6. RAG Retrieval from Course Materials
        retrieved_chunks = self._retrieve_rag_context(
            subject_id=assignment.subject_id,
            query_terms=query_terms,
        )

        return AssessmentContext(
            submission=submission,
            assignment_title=assignment.title,
            assignment_description=clean_description,
            total_max_marks=total_max_marks,
            questions=questions_data,
            rubric_items=rubric_items_data,
            submission_text=submission_text,
            retrieved_chunks=retrieved_chunks,
            knowledge_context_available=len(retrieved_chunks) > 0,
            file_format=file_format,
            file_manifest=file_manifest,
            execution_audit=execution_audit,
            assignment_instructions=clean_instructions,
            assignment_documents_text=assignment_documents_text,
            zip_inventory=zip_inventory,
            original_archive_name=original_archive_name,
        )

    def _resolve_submission_payload(
        self,
        submission: Submission,
        rubric_items: list[dict[str, Any]] | None = None,
        assignment_instructions: str | None = None,
        assignment_title: str | None = None,
    ) -> tuple[str, str | None, dict[str, Any] | None, dict[str, Any] | None, Any | None, str | None]:
        """
        Extract text and structured metadata from submission text or file.
        Supports:
          - Multi-file ZIP projects (.zip) with dynamic rubric mapping and diagnostics
          - Jupyter Notebooks (.ipynb)
          - Source code files (.py, .java, .cpp, .js, .ts, etc.)
          - Tabular datasets (.csv, .tsv) with metrics and distinct configs
          - Documents (.pdf, .docx, .txt, .md, .json)
        """
        text_parts: list[str] = []
        file_format: str | None = None
        file_manifest: dict[str, Any] | None = None
        execution_audit: dict[str, Any] | None = None
        zip_inventory: Any | None = None
        original_archive_name: str | None = None

        if submission.submission_text and submission.submission_text.strip():
            text_parts.append(f"=== STUDENT TEXT ANSWER ===\n{submission.submission_text.strip()}")

        if submission.file_path:
            file_p = Path(submission.file_path)
            orig_name = submission.original_filename or file_p.name
            if file_p.exists():
                try:
                    ext = file_p.suffix.lower()
                    file_format = ext.lstrip(".")

                    if ext == ".ipynb":
                        nb_processor = get_notebook_processor()
                        parsed_nb = nb_processor.parse_file(file_p, filename=orig_name)
                        text_parts.append(parsed_nb.text_representation)
                        execution_audit = {
                            "total_cells": parsed_nb.audit.total_cells,
                            "code_cells": parsed_nb.audit.code_cells,
                            "executed_code_cells": parsed_nb.audit.executed_code_cells,
                            "unexecuted_code_cells": parsed_nb.audit.unexecuted_code_cells,
                            "cells_with_errors": parsed_nb.audit.cells_with_errors,
                            "execution_status": parsed_nb.audit.execution_status,
                            "execution_order_anomaly": parsed_nb.audit.execution_order_anomaly,
                            "kernel_language": parsed_nb.audit.kernel_language,
                        }
                    elif ext == ".zip":
                        zip_proc = get_zip_processor()
                        unpack_dir = get_archive_unpacked_dir(file_p)
                        manifest = zip_proc.inspect_and_extract(file_p, target_extract_dir=unpack_dir)
                        zip_inventory = manifest
                        original_archive_name = orig_name
                        evidence = zip_proc.build_evidence_package(
                            manifest=manifest,
                            archive_name=orig_name,
                            rubric_items=rubric_items,
                            assignment_instructions=assignment_instructions,
                            assignment_title=assignment_title,
                        )
                        text_parts.append(evidence)

                        report = zip_proc.generate_evidence_report(
                            submission_id=submission.id,
                            inventory=manifest,
                            original_filename=orig_name,
                        )
                        file_manifest = {
                            "total_files": manifest.total_files,
                            "total_size_bytes": manifest.total_size_bytes,
                            "category_counts": manifest.category_counts,
                            "has_readme": manifest.has_readme,
                            "has_tests": manifest.has_tests,
                            "has_manifest": manifest.has_manifest,
                            "notebook_count": len(manifest.notebooks),
                            "files": [
                                {
                                    "rel_path": e.rel_path,
                                    "size": e.size_bytes,
                                    "category": e.category,
                                    "extension": e.extension,
                                    "is_test": e.is_test,
                                }
                                for e in manifest.file_entries
                            ],
                            "evidence_report": report,
                        }
                        if manifest.notebooks:
                            first_nb = manifest.notebooks[0]
                            execution_audit = {
                                "total_cells": first_nb.audit.total_cells,
                                "code_cells": first_nb.audit.code_cells,
                                "executed_code_cells": first_nb.audit.executed_code_cells,
                                "unexecuted_code_cells": first_nb.audit.unexecuted_code_cells,
                                "cells_with_errors": first_nb.audit.cells_with_errors,
                                "execution_status": first_nb.audit.execution_status,
                                "execution_order_anomaly": first_nb.audit.execution_order_anomaly,
                                "kernel_language": first_nb.audit.kernel_language,
                            }
                    elif ext in [".py", ".java", ".cpp", ".c", ".h", ".cs", ".js", ".ts", ".html", ".css", ".r", ".sql", ".sh"]:
                        raw_code = file_p.read_text(encoding="utf-8", errors="replace")
                        line_count = len(raw_code.splitlines())
                        text_parts.append(
                            f"=== SOURCE CODE FILE: {orig_name} ({line_count} lines) ===\n"
                            f">>> CODE CONTENT:\n{raw_code}"
                        )
                    elif ext == ".pdf":
                        extracted = extract_text_from_pdf(file_p)
                        if extracted and len(extracted.strip()) >= 50:
                            text_parts.append(f"=== SUBMITTED DOCUMENT: {orig_name} ===\n{extracted}")
                        else:
                            text_parts.append(
                                f"=== SUBMITTED DOCUMENT: {orig_name} ===\n"
                                "[Notice: Scanned or image-only PDF with minimal/no extractable text (<50 characters).]"
                            )
                    elif ext in [".docx", ".doc"]:
                        extracted = extract_text_from_docx(file_p)
                        if extracted:
                            text_parts.append(f"=== SUBMITTED DOCUMENT: {orig_name} ===\n{extracted}")
                    elif ext in [".txt", ".md", ".json"]:
                        raw_text = file_p.read_text(encoding="utf-8", errors="replace")
                        text_parts.append(f"=== SUBMITTED FILE: {orig_name} ===\n{raw_text}")
                    elif ext == ".csv":
                        zip_proc = get_zip_processor()
                        summary, content, useful, reason = zip_proc._process_tabular_data(file_p)
                        text_parts.append(f"=== SUBMITTED DATA FILE: {orig_name} ===\n{content}")
                except Exception as exc:
                    logger.warning("Could not extract text from submission file %s: %s", file_p, exc)
                    text_parts.append(f"[Error reading file {orig_name}: {exc}]")

        settings = get_settings()
        full_text = "\n\n".join(text_parts).strip()
        if len(full_text) > settings.max_submission_evidence_chars:
            full_text = (
                full_text[: settings.max_submission_evidence_chars]
                + f"\n... [Submission evidence truncated at {settings.max_submission_evidence_chars} characters for AI assessment] ..."
            )
        return full_text, file_format, file_manifest, execution_audit, zip_inventory, original_archive_name

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
            settings = get_settings()
            max_rag = settings.max_rag_context_chars
            selected_chunks: list[dict[str, Any]] = []
            acc_len = 0

            for c in chunks:
                rem = max_rag - acc_len
                if rem <= 80:
                    break
                text = c.chunk_text
                if len(text) > rem:
                    text = text[:rem] + " ... [chunk truncated]"
                acc_len += len(text)
                selected_chunks.append({
                    "chunk_text": text,
                    "similarity": c.similarity,
                    "metadata": c.metadata.model_dump() if hasattr(c.metadata, "model_dump") else c.metadata,
                })

            return selected_chunks
        except Exception as exc:
            logger.warning("RAG retrieval failed or vector store not initialized: %s", exc)
            return []


_prep_service_instance: AssessmentPreparationService | None = None


def get_assessment_preparation_service() -> AssessmentPreparationService:
    global _prep_service_instance
    if _prep_service_instance is None:
        _prep_service_instance = AssessmentPreparationService()
    return _prep_service_instance
