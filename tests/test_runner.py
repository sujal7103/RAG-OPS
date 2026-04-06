"""Integration test for the benchmark runner."""

import pytest


def test_runner_with_mock_embedder(monkeypatch):
    """Test the full pipeline using a mock embedder (no real model needed)."""
    import numpy as np

    # Mock the embed_texts function to return random embeddings
    def mock_embed(texts, embedder_name, api_keys=None, is_query=False):
        return np.random.randn(len(texts), 32).astype(np.float32)

    monkeypatch.setattr("rag_ops.runner.embed_texts", mock_embed)

    from rag_ops.runner import run_benchmark

    documents = [
        {"doc_id": "d1", "content": "Python is a programming language created by Guido."},
        {"doc_id": "d2", "content": "JavaScript runs in the browser and on Node.js servers."},
        {"doc_id": "d3", "content": "Rust is a systems language focused on memory safety."},
    ]
    queries = [
        {"query_id": "q1", "query": "What is Python?"},
        {"query_id": "q2", "query": "Tell me about JavaScript"},
    ]
    ground_truth = {
        "q1": {"d1"},
        "q2": {"d2"},
    }

    df, per_query = run_benchmark(
        documents=documents,
        queries=queries,
        ground_truth=ground_truth,
        chunker_names=["Fixed Size"],
        embedder_names=["MiniLM"],
        retriever_names=["Dense", "Sparse"],
        top_k=3,
    )

    # Should have 2 rows (1 chunker * 1 embedder * 2 retrievers)
    assert len(df) == 2
    assert "precision@k" in df.columns
    assert "recall@k" in df.columns
    assert "mrr" in df.columns

    # All metrics should be between 0 and 1
    for col in ["precision@k", "recall@k", "mrr", "ndcg@k", "map@k", "hit_rate@k"]:
        assert (df[col] >= 0).all()
        assert (df[col] <= 1).all()

    # Per-query results should exist
    assert len(per_query) == 2
    for label, details in per_query.items():
        assert len(details) == 2  # 2 queries
