"""
Embedding provider abstraction and implementations for RAG.

Decouples the system from any single embedding provider (Chroma ONNX default, Mock, OpenAI, etc.).
"""

import hashlib
import math
from abc import ABC, abstractmethod

from app.core.config import get_settings


class BaseEmbeddingProvider(ABC):
    """Abstract base class for text embedding generation."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of document strings."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Generate a vector embedding for a single query string."""
        pass


class ChromaDefaultEmbeddingProvider(BaseEmbeddingProvider):
    """
    Default embedding provider utilizing ChromaDB's bundled ONNX all-MiniLM-L6-v2 model.
    Produces 384-dimensional dense vectors locally without external API dependencies.
    """

    def __init__(self) -> None:
        from chromadb.utils import embedding_functions

        self._fn = embedding_functions.DefaultEmbeddingFunction()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._fn(texts)
        # Ensure return type is list of float lists
        return [list(map(float, emb)) for emb in embeddings]

    def embed_query(self, text: str) -> list[float]:
        res = self.embed_documents([text])
        return res[0] if res else [0.0] * 384


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic pseudo-embedding provider for fast unit tests and environments
    without ONNX runtime overhead. Produces normalized 384-dimensional vectors.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _generate_vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        if not text:
            return vector

        # Create deterministic pseudo-features based on character hashes
        for i, word in enumerate(text.lower().split()):
            h = int(hashlib.md5(f"{word}:{i}".encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vector[idx] += 1.0

        # L2 normalize vector
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0.0:
            vector = [v / norm for v in vector]
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._generate_vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._generate_vector(text)


class EmbeddingService:
    """Configurable embedding service adhering to project settings."""

    def __init__(self, provider: BaseEmbeddingProvider | None = None) -> None:
        if provider is not None:
            self.provider = provider
        else:
            settings = get_settings()
            provider_type = (settings.embedding_provider or "default").lower()
            if provider_type == "mock":
                self.provider = MockEmbeddingProvider()
            else:
                self.provider = ChromaDefaultEmbeddingProvider()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.provider.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.provider.embed_query(text)


_embedding_service_instance: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Dependency / singleton accessor for the embedding service."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
