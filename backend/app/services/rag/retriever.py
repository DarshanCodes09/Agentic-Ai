"""
Academic knowledge retriever service for semantic search across course materials.
"""

from typing import Any

from app.core.config import get_settings
from app.schemas.course_material import ChunkSearchResult
from app.services.rag.vector_store import VectorStoreService, get_vector_store_service


class AcademicRetriever:
    """Service for querying authoritative academic knowledge without calling an LLM."""

    def __init__(self, vector_store: VectorStoreService | None = None) -> None:
        self.vector_store = vector_store or get_vector_store_service()

    def retrieve(
        self,
        query: str,
        subject_id: int | None = None,
        course_material_id: int | None = None,
        top_k: int | None = None,
    ) -> list[ChunkSearchResult]:
        """
        Retrieve relevant course material chunks matching a semantic query.

        Args:
            query: Question or concept to look up in the academic knowledge base.
            subject_id: Optional ID to restrict search to a specific subject.
            course_material_id: Optional ID to restrict search to a single document.
            top_k: Number of chunks to retrieve (defaults to config setting).

        Returns:
            List of ChunkSearchResult models containing chunk text, similarity, and metadata.
        """
        settings = get_settings()
        k = top_k if top_k is not None and top_k > 0 else settings.retrieval_top_k

        raw_results = self.vector_store.query_similar(
            query_text=query,
            top_k=k,
            subject_id=subject_id,
            course_material_id=course_material_id,
        )

        return [
            ChunkSearchResult(
                chunk_text=r["chunk_text"],
                similarity=r.get("similarity"),
                metadata=r["metadata"],
            )
            for r in raw_results
        ]


_retriever_instance: AcademicRetriever | None = None


def get_academic_retriever() -> AcademicRetriever:
    """Dependency / singleton accessor for AcademicRetriever."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = AcademicRetriever()
    return _retriever_instance
