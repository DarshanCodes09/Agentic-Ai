"""
Tests for RAG services: embeddings, vector store, and semantic retrieval — Phase 3.
"""

from pathlib import Path

import pytest

from app.services.document_processing.chunker import TextChunk
from app.services.rag.embeddings import (
    ChromaDefaultEmbeddingProvider,
    EmbeddingService,
    MockEmbeddingProvider,
)
from app.services.rag.retriever import AcademicRetriever
from app.services.rag.vector_store import VectorStoreService


# ---------------------------------------------------------------------------
# 1. Embedding Provider Tests
# ---------------------------------------------------------------------------

def test_mock_embedding_provider():
    provider = MockEmbeddingProvider(dimension=384)
    texts = ["Distributed transactions with two-phase commit", "B-Tree database indexes"]
    vectors = provider.embed_documents(texts)

    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384
    # Query embedding
    q_vec = provider.embed_query("two-phase commit")
    assert len(q_vec) == 384


def test_chroma_default_embedding_provider():
    provider = ChromaDefaultEmbeddingProvider()
    vectors = provider.embed_documents(["Relational algebra", "Vector databases"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 384


def test_embedding_service_abstraction():
    mock_prov = MockEmbeddingProvider()
    service = EmbeddingService(provider=mock_prov)
    vecs = service.embed_documents(["Test doc"])
    assert len(vecs) == 1
    assert len(vecs[0]) == 384


# ---------------------------------------------------------------------------
# 2. Vector Store & Retrieval Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def test_vector_store(tmp_path: Path) -> VectorStoreService:
    store_dir = tmp_path / "chroma_test_store"
    # Use mock embeddings for fast, deterministic, offline vector tests
    mock_embeddings = EmbeddingService(provider=MockEmbeddingProvider())
    return VectorStoreService(persist_directory=str(store_dir), embedding_service=mock_embeddings)


def test_vector_store_add_and_query(test_vector_store: VectorStoreService):
    chunks = [
        TextChunk(
            text="Quantum computing leverages superposition and quantum entanglement.",
            chunk_index=0,
            subject_id=1,
            course_material_id=101,
            source_filename="physics.pdf",
        ),
        TextChunk(
            text="Relational database management systems use SQL for query processing.",
            chunk_index=0,
            subject_id=2,
            course_material_id=102,
            source_filename="databases.pdf",
        ),
    ]

    added = test_vector_store.add_chunks(chunks)
    assert added == 2

    # Query without filter
    results = test_vector_store.query_similar("quantum superposition", top_k=2)
    assert len(results) > 0
    assert any("Quantum computing" in r["chunk_text"] for r in results)


def test_vector_store_filtering(test_vector_store: VectorStoreService):
    chunks = [
        TextChunk(
            text="Compiler design uses lexing, parsing, and abstract syntax trees.",
            chunk_index=0,
            subject_id=10,
            course_material_id=201,
            source_filename="compilers.pdf",
        ),
        TextChunk(
            text="Computer graphics uses rasterization and ray tracing shaders.",
            chunk_index=0,
            subject_id=20,
            course_material_id=202,
            source_filename="graphics.pdf",
        ),
    ]
    test_vector_store.add_chunks(chunks)

    # Filter by subject_id 10
    res_subj = test_vector_store.query_similar(
        query_text="syntax trees",
        subject_id=10,
        top_k=2,
    )
    assert len(res_subj) == 1
    assert res_subj[0]["metadata"]["subject_id"] == 10

    # Filter by course_material_id 202
    res_mat = test_vector_store.query_similar(
        query_text="shaders",
        course_material_id=202,
        top_k=2,
    )
    assert len(res_mat) == 1
    assert res_mat[0]["metadata"]["course_material_id"] == 202


def test_vector_store_delete_material_chunks(test_vector_store: VectorStoreService):
    chunk = TextChunk(
        text="Temporary lecture notes to be deleted.",
        chunk_index=0,
        subject_id=5,
        course_material_id=999,
        source_filename="temp.pdf",
    )
    test_vector_store.add_chunks([chunk])

    # Verify presence
    res_before = test_vector_store.query_similar("temporary lecture notes", course_material_id=999)
    assert len(res_before) == 1

    # Delete material chunks
    test_vector_store.delete_material_chunks(999)

    # Verify absence
    res_after = test_vector_store.query_similar("temporary lecture notes", course_material_id=999)
    assert len(res_after) == 0


def test_academic_retriever(test_vector_store: VectorStoreService):
    retriever = AcademicRetriever(vector_store=test_vector_store)
    chunk = TextChunk(
        text="A hash table provides expected O(1) amortized lookup complexity.",
        chunk_index=0,
        subject_id=3,
        course_material_id=301,
        source_filename="dsa.docx",
    )
    test_vector_store.add_chunks([chunk])

    retrieved = retriever.retrieve("hash table lookup complexity", subject_id=3, top_k=1)
    assert len(retrieved) == 1
    assert "O(1)" in retrieved[0].chunk_text
    assert retrieved[0].similarity is not None
    assert retrieved[0].metadata["subject_id"] == 3
