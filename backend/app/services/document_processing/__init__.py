"""
Document processing package.

Extracts text from academic PDFs and DOCX files, cleans text, and chunks
deterministically for vector embedding and retrieval.
"""

from app.services.document_processing.chunker import TextChunk, chunk_text
from app.services.document_processing.docx_processor import extract_text_from_docx
from app.services.document_processing.notebook_processor import NotebookProcessor, get_notebook_processor
from app.services.document_processing.pdf_processor import extract_text_from_pdf
from app.services.document_processing.text_cleaner import clean_text
from app.services.document_processing.zip_processor import ZipProcessor, get_zip_processor

__all__ = [
    "clean_text",
    "extract_text_from_pdf",
    "extract_text_from_docx",
    "chunk_text",
    "TextChunk",
    "NotebookProcessor",
    "get_notebook_processor",
    "ZipProcessor",
    "get_zip_processor",
]
