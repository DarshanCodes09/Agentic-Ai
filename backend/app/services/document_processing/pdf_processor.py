"""
PDF text extractor using PyMuPDF (fitz).
"""

from pathlib import Path

import fitz  # PyMuPDF

from app.core.exceptions import AppException
from app.services.document_processing.text_cleaner import clean_text


def extract_text_from_pdf(file_source: str | Path | bytes) -> str:
    """
    Extract text content from a PDF file path or byte stream using PyMuPDF.

    Args:
        file_source: Absolute/relative file path or raw PDF bytes.

    Returns:
        Cleaned extracted text string.

    Raises:
        AppException: If file cannot be read or parsed as a valid PDF.
    """
    doc = None
    try:
        if isinstance(file_source, bytes):
            doc = fitz.open(stream=file_source, filetype="pdf")
        else:
            path = Path(file_source)
            if not path.exists():
                raise AppException(f"PDF file not found at: {path}", status_code=404)
            doc = fitz.open(str(path))

        page_texts: list[str] = []
        for page in doc:
            text = page.get_text("text")
            if text:
                page_texts.append(text)

        full_raw_text = "\n\n".join(page_texts)
        return clean_text(full_raw_text)

    except Exception as exc:
        if isinstance(exc, AppException):
            raise
        raise AppException(f"Failed to extract text from PDF: {exc}", status_code=422) from exc
    finally:
        if doc is not None:
            doc.close()
