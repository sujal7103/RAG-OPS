"""Tests for retrieval helpers and fallback paths."""

import numpy as np

from rag_ops.retrievers import (
    dense_retrieve,
    hybrid_retrieve,
    prepare_retriever_resources,
    sparse_retrieve,
)


CHUNKS = [
    {"chunk_id": "c1", "doc_id": "d1", "text": "python lists tuples dictionaries"},
    {"chunk_id": "c2", "doc_id": "d2", "text": "javascript browser node runtime"},
    {"chunk_id": "c3", "doc_id": "d3", "text": "python pytest unit testing"},
]


def test_dense_retrieve_numpy_fallback_returns_ranked_results():
    query_embedding = np.array([1.0, 0.0], dtype=np.float32)
    corpus_embeddings = np.array(
        [[0.9, 0.1], [0.1, 0.9], [0.8, 0.2]],
        dtype=np.float32,
    )

    results = dense_retrieve(query_embedding, corpus_embeddings, CHUNKS, top_k=2)

    assert [result["doc_id"] for result in results] == ["d1", "d3"]


def test_sparse_retrieve_fallback_finds_keyword_matches():
    results = sparse_retrieve("python testing", CHUNKS, top_k=2)

    assert results
    assert results[0]["doc_id"] == "d3"


def test_hybrid_retrieve_uses_prepared_resources():
    query_embedding = np.array([1.0, 0.0], dtype=np.float32)
    corpus_embeddings = np.array(
        [[0.9, 0.1], [0.1, 0.9], [0.8, 0.2]],
        dtype=np.float32,
    )
    resources = prepare_retriever_resources(["Dense", "Sparse", "Hybrid"], corpus_embeddings, CHUNKS)

    results = hybrid_retrieve(
        "python lists",
        query_embedding,
        corpus_embeddings,
        CHUNKS,
        top_k=2,
        dense_index=resources["dense"],
        sparse_index=resources["sparse"],
    )

    assert len(results) == 2
    assert results[0]["doc_id"] in {"d1", "d3"}

