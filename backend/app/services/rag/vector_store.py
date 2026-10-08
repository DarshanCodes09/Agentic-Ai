"""
ChromaDB vector store service for persisting and querying academic chunks.
"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings
from app.services.document_processing.chunker import TextChunk
from app.services.rag.embeddings import EmbeddingService, get_embedding_service


class VectorStoreService:
    """Manages the local persistent ChromaDB collection for academic knowledge."""

    COLLECTION_NAME = "academic_knowledge"

    def __init__(
        self,
        persist_directory: str | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        settings = get_settings()
        if persist_directory is None:
            # Resolve relative to project root or use configured path
            raw_path = Path(settings.chroma_persist_dir)
            if not raw_path.is_absolute():
                project_root = Path(__file__).resolve().parent.parent.parent.parent
                self.persist_dir = project_root / settings.chroma_persist_dir.lstrip("./\\")
            else:
                self.persist_dir = raw_path
        else:
            self.persist_dir = Path(persist_directory)

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_service = embedding_service or get_embedding_service()

        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "Authoritative faculty course materials"},
        )

    def add_chunks(self, chunks: list[TextChunk]) -> int:
        """
        Embed and persist text chunks into ChromaDB with metadata.

        Returns:
            Number of chunks added.
        """
        if not chunks:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for chunk in chunks:
            chunk_id = f"mat_{chunk.course_material_id}_chunk_{chunk.chunk_index}"
            ids.append(chunk_id)
            documents.append(chunk.text)
            metadatas.append(chunk.metadata)

        embeddings = self.embedding_service.embed_documents(documents)

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(chunks)

    def delete_material_chunks(self, course_material_id: int) -> None:
        """Remove all vector chunks associated with a specific CourseMaterial ID."""
        try:
            self._collection.delete(where={"course_material_id": course_material_id})
        except Exception:
            pass

    def query_similar(
        self,
        query_text: str,
        top_k: int = 4,
        subject_id: int | None = None,
        course_material_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform semantic similarity search over stored course material chunks.

        Args:
            query_text: Natural language query string.
            top_k: Number of most relevant chunks to return.
            subject_id: Optional filter for a specific subject.
            course_material_id: Optional filter for a specific material.

        Returns:
            List of dictionaries containing 'chunk_text', 'similarity', and 'metadata'.
        """
        query_vector = self.embedding_service.embed_query(query_text)

        # Build ChromaDB metadata filter
        where_filter: dict[str, Any] | None = None
        conditions: list[dict[str, Any]] = []

        if subject_id is not None:
            conditions.append({"subject_id": subject_id})
        if course_material_id is not None:
            conditions.append({"course_material_id": course_material_id})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        # Query collection
        query_args: dict[str, Any] = {
            "query_embeddings": [query_vector],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_args["where"] = where_filter

        results = self._collection.query(**query_args)

        output: list[dict[str, Any]] = []
        docs = results.get("documents", [[]])[0] if results.get("documents") else []
        metas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []

        for doc, meta, dist in zip(docs, metas, distances):
            # Convert L2 / cosine distance to a normalized similarity score (0 to 1)
            similarity = 1.0 / (1.0 + float(dist)) if dist is not None else 1.0
            output.append(
                {
                    "chunk_text": doc,
                    "metadata": meta,
                    "similarity": round(similarity, 4),
                }
            )

        return output


_vector_store_instance: VectorStoreService | None = None


def get_vector_store_service() -> VectorStoreService:
    """Dependency / singleton accessor for the vector store."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStoreService()
    return _vector_store_instance
