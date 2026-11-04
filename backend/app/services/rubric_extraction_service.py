"""
Rubric and assignment specification extraction service.

Extracts text from faculty-attached assignment files (PDF, DOCX, TXT, MD) and uses
the LLM service to detect grading schemes, criteria breakdowns, mark allocations,
and assignment instructions.
"""

import io
import logging
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.schemas.rubric import ExtractedRubricItem, ExtractedRubricResponse
from app.services.document_processing.docx_processor import extract_text_from_docx
from app.services.document_processing.pdf_processor import extract_text_from_pdf
from app.services.document_processing.text_cleaner import clean_text
from app.services.llm.client import get_llm_service

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

SYSTEM_RUBRIC_EXTRACTION_PROMPT = """You are an expert University Curriculum and Academic Assessment specialist.
Your task is to analyze the provided faculty assignment document and extract any explicit evaluation rubric, marking scheme, or grading breakdown.

Extraction Instructions:
1. Criteria Identification: Look for explicit criteria, deliverables, sections, tasks, or components that have designated marks, percentages, or points.
2. Marks Distribution: For each criterion, extract the allocated max_marks.
3. Criteria Descriptions: Include relevant requirements, expectations, or benchmarks for that criterion.
4. Total Marks: Calculate the sum of marks across all extracted criteria.
5. Rubric Verification: If the document contains assignment instructions, problem descriptions, or code requirements, but DOES NOT contain an explicit marking scheme or rubric breakdown with allocated marks, set has_rubric = false and return an empty items list.
6. NO FABRICATION: Do NOT invent, assume, or hallucinate rubric criteria or mark distributions that are not explicitly stated in the document.
7. Return strictly valid JSON conforming to ExtractedRubricResponse schema.
"""


class RubricExtractionService:
    """Service for extracting text and grading rubrics from academic assignment files."""

    def extract_text_from_file_bytes(self, content: bytes, filename: str) -> str:
        """
        Extract text from raw file bytes based on file extension.
        Supports PDF, DOCX, TXT, and Markdown.
        """
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise AppException(
                detail=f"Unsupported file type '{ext}'. Allowed types: PDF, DOCX, TXT, MD.",
                status_code=422,
            )

        if not content or len(content.strip()) == 0:
            raise AppException(
                detail="Uploaded file is empty.",
                status_code=422,
            )

        try:
            if ext == ".pdf":
                text = extract_text_from_pdf(content)
            elif ext == ".docx":
                text = extract_text_from_docx(content)
            elif ext in (".txt", ".md"):
                # Handle UTF-8 with fallback decoding
                try:
                    raw_text = content.decode("utf-8")
                except UnicodeDecodeError:
                    raw_text = content.decode("latin-1", errors="replace")
                text = clean_text(raw_text)
            else:
                raise AppException(f"Unsupported extension: {ext}", status_code=422)

            if not text or not text.strip():
                raise AppException(
                    detail="No readable text could be extracted from the document.",
                    status_code=422,
                )

            return text.strip()
        except AppException:
            raise
        except Exception as exc:
            logger.error("Failed to extract text from %s: %s", filename, exc)
            raise AppException(
                detail=f"Failed to read document text: {exc}",
                status_code=422,
            ) from exc

    def extract_text_from_path(self, file_path: Path | str) -> str:
        """Extract text from a saved file on disk."""
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            raise AppException(f"File not found at: {p}", status_code=404)
        content = p.read_bytes()
        return self.extract_text_from_file_bytes(content, p.name)

    async def extract_rubric_from_upload(
        self,
        file: UploadFile,
        expected_max_marks: float | None = None,
    ) -> ExtractedRubricResponse:
        """Extract text from an uploaded assignment file and parse rubric via LLM."""
        filename = file.filename or "assignment_file"
        content = await file.read()
        await file.seek(0)

        # Validate file size
        max_bytes = get_settings().max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise AppException(
                detail=f"File exceeds maximum upload size of {get_settings().max_upload_size_mb}MB.",
                status_code=413,
            )

        doc_text = self.extract_text_from_file_bytes(content, filename)
        return await self.extract_rubric_from_text(
            doc_text=doc_text,
            filename=filename,
            expected_max_marks=expected_max_marks,
        )

    async def extract_rubric_from_text(
        self,
        doc_text: str,
        filename: str = "",
        expected_max_marks: float | None = None,
    ) -> ExtractedRubricResponse:
        """
        Use the LLM service to analyze document text and extract structured rubric.
        """
        # Bounded snippet for rubric extraction prompt (first 12,000 characters is plenty for marking scheme)
        snippet = doc_text[:12000]

        max_marks_info = (
            f"\nNote: The assignment's configured Maximum Marks is {expected_max_marks}."
            if expected_max_marks and expected_max_marks > 0
            else ""
        )

        user_prompt = (
            f"Analyze the following assignment specification document ({filename}) to extract "
            f"any explicit grading rubric or marking criteria breakdown.{max_marks_info}\n\n"
            f"--- BEGIN ASSIGNMENT DOCUMENT ---\n"
            f"{snippet}\n"
            f"--- END ASSIGNMENT DOCUMENT ---\n\n"
            f"Extract the criteria, mark allocations, and descriptions if present. "
            f"If there is no explicit rubric or marking breakdown, set has_rubric to false."
        )

        llm_service = get_llm_service()

        try:
            result: ExtractedRubricResponse = await llm_service.generate_structured(
                prompt=f"{SYSTEM_RUBRIC_EXTRACTION_PROMPT}\n\n{user_prompt}",
                response_model=ExtractedRubricResponse,
            )
        except Exception as exc:
            logger.error("LLM rubric extraction failed for %s: %s", filename, exc)
            raise AppException(
                detail=f"Failed to analyze rubric from document: {exc}",
                status_code=502,
            ) from exc

        # Post-process and sanitize result
        if result.items:
            valid_items: list[ExtractedRubricItem] = []
            for item in result.items:
                c_name = item.criterion.strip() if item.criterion else ""
                if c_name and item.max_marks > 0:
                    valid_items.append(
                        ExtractedRubricItem(
                            criterion=c_name,
                            description=item.description.strip() if item.description else None,
                            max_marks=round(float(item.max_marks), 2),
                        )
                    )
            result.items = valid_items
            result.has_rubric = len(valid_items) > 0
            result.total_marks = round(sum(i.max_marks for i in valid_items), 2)

            if not result.rubric_name:
                stem = Path(filename).stem.replace("_", " ").title() if filename else "Assignment"
                result.rubric_name = f"{stem} Rubric"

            # Check for total marks mismatch against expected assignment max_marks
            if expected_max_marks and expected_max_marks > 0:
                if abs(result.total_marks - expected_max_marks) > 0.01:
                    result.message = (
                        f"Extracted {len(valid_items)} criteria totaling {result.total_marks} marks. "
                        f"Note: This differs from the assignment maximum marks ({expected_max_marks}). "
                        "Please adjust criteria marks to balance before saving."
                    )
                else:
                    result.message = f"Successfully extracted balanced rubric ({len(valid_items)} criteria totaling {result.total_marks} marks)."
            else:
                result.message = f"Extracted {len(valid_items)} criteria totaling {result.total_marks} marks."
        else:
            result.has_rubric = False
            result.total_marks = None
            result.items = []
            result.message = (
                "No explicit grading rubric was found in the document. "
                "The file will still be attached to provide assignment instructions and requirements for AI evaluation."
            )

        # Include short preview of extracted text for faculty inspection
        preview_len = min(600, len(doc_text))
        result.extracted_text_preview = doc_text[:preview_len] + ("..." if len(doc_text) > preview_len else "")

        return result


_rubric_extraction_service: RubricExtractionService | None = None


def get_rubric_extraction_service() -> RubricExtractionService:
    global _rubric_extraction_service
    if _rubric_extraction_service is None:
        _rubric_extraction_service = RubricExtractionService()
    return _rubric_extraction_service
