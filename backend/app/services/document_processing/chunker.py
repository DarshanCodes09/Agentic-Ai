"""
Deterministic text chunking for academic reference materials.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TextChunk:
    """Represents an individual text chunk with associated document metadata."""
    text: str
    chunk_index: int
    subject_id: int
    course_material_id: int
    source_filename: str

    @property
    def metadata(self) -> dict[str, Any]:
        """Metadata dictionary formatted for vector store storage."""
        return {
            "subject_id": self.subject_id,
            "course_material_id": self.course_material_id,
            "source_filename": self.source_filename,
            "chunk_index": self.chunk_index,
        }


def chunk_text(
    text: str,
    subject_id: int,
    course_material_id: int,
    source_filename: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[TextChunk]:
    """
    Split text into deterministic overlapping chunks with source metadata.

    Args:
        text: Normalized input text string.
        subject_id: ID of the subject this document belongs to.
        course_material_id: ID of the source CourseMaterial record.
        source_filename: Original filename of the document.
        chunk_size: Maximum character count per chunk.
        chunk_overlap: Number of characters shared between consecutive chunks.

    Returns:
        List of TextChunk instances.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    if chunk_size <= 0:
        chunk_size = 500
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        chunk_overlap = min(50, chunk_size // 2)

    step = chunk_size - chunk_overlap
    chunks: list[TextChunk] = []
    chunk_index = 0
    start = 0
    total_length = len(cleaned)

    while start < total_length:
        end = min(start + chunk_size, total_length)

        # If not at the very end of text, attempt to break nicely on a word boundary
        if end < total_length:
            last_space = cleaned.rfind(" ", start, end)
            if last_space > start + (chunk_size // 2):
                end = last_space

        chunk_str = cleaned[start:end].strip()
        if chunk_str:
            chunks.append(
                TextChunk(
                    text=chunk_str,
                    chunk_index=chunk_index,
                    subject_id=subject_id,
                    course_material_id=course_material_id,
                    source_filename=source_filename,
                )
            )
            chunk_index += 1

        # Advance window
        if end >= total_length:
            break
        start += step
        if start >= end:
            start = end

    return chunks
