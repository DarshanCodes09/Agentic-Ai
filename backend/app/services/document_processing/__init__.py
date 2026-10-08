"""
Document processing package.

Extracts text from academic PDFs and DOCX files, cleans text, and chunks
deterministically for vector embedding and retrieval.
"""

from app.services.document_processing.chunker import TextChunk, chunk_text
from app.services.document_processing.docx_processor import extract_text_from_docx
from app.services.document_processing.pdf_processor import extract_text_from_pdf
from app.services.document_processing.text_cleaner import clean_text

__all__ = [
    "clean_text",
    "extract_text_from_pdf",
    "extract_text_from_docx",
    "chunk_text",
    "TextChunk",
]
