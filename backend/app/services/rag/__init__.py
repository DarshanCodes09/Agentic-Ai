"""
RAG (Retrieval-Augmented Generation) package.

Provides embeddings, local persistent ChromaDB vector storage, and semantic retrieval
for academic course materials.
"""

from app.services.rag.embeddings import (
    BaseEmbeddingProvider,
    ChromaDefaultEmbeddingProvider,
    EmbeddingService,
    MockEmbeddingProvider,
    get_embedding_service,
)
from app.services.rag.retriever import AcademicRetriever, get_academic_retriever
from app.services.rag.vector_store import VectorStoreService, get_vector_store_service

__all__ = [
    "BaseEmbeddingProvider",
    "ChromaDefaultEmbeddingProvider",
    "MockEmbeddingProvider",
    "EmbeddingService",
    "get_embedding_service",
    "VectorStoreService",
    "get_vector_store_service",
    "AcademicRetriever",
    "get_academic_retriever",
]
