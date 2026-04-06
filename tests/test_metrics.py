"""Tests for evaluation metrics."""

from rag_ops.metrics import (
    precision_at_k,
    recall_at_k,
    mrr,
    ndcg_at_k,
    map_at_k,
    hit_rate_at_k,
    evaluate_query,
)


def test_precision_at_k():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c"}
    assert precision_at_k(retrieved, relevant, 3) == 2 / 3
    assert precision_at_k(retrieved, relevant, 5) == 2 / 5
    assert precision_at_k(retrieved, relevant, 1) == 1.0


def test_precision_no_hits():
    assert precision_at_k(["x", "y"], {"a"}, 2) == 0.0


def test_recall_at_k():
    retrieved = ["a", "b", "c"]
    relevant = {"a", "c", "e"}
    assert recall_at_k(retrieved, relevant, 3) == 2 / 3
    assert recall_at_k(retrieved, relevant, 1) == 1 / 3


def test_recall_empty_relevant():
    assert recall_at_k(["a"], set(), 1) == 0.0


def test_mrr():
    assert mrr(["x", "a", "b"], {"a"}) == 0.5
    assert mrr(["a", "b", "c"], {"a"}) == 1.0
    assert mrr(["x", "y", "z"], {"a"}) == 0.0


def test_ndcg_at_k():
    retrieved = ["a", "x", "b"]
    relevant = {"a", "b"}
    score = ndcg_at_k(retrieved, relevant, 3)
    assert 0 < score <= 1.0


def test_ndcg_perfect():
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b", "c"}
    assert ndcg_at_k(retrieved, relevant, 3) == 1.0


def test_map_at_k():
    retrieved = ["a", "x", "b"]
    relevant = {"a", "b"}
    score = map_at_k(retrieved, relevant, 3)
    # AP = (1/1 + 2/3) / 2 = 0.833...
    assert abs(score - 0.8333) < 0.01


def test_hit_rate():
    assert hit_rate_at_k(["x", "a"], {"a"}, 2) == 1.0
    assert hit_rate_at_k(["x", "y"], {"a"}, 2) == 0.0


def test_evaluate_query():
    result = evaluate_query(["a", "b", "c"], {"a", "c"}, 3)
    assert "precision@k" in result
    assert "recall@k" in result
    assert "mrr" in result
    assert "ndcg@k" in result
    assert "map@k" in result
    assert "hit_rate@k" in result
    assert result["precision@k"] == 2 / 3
    assert result["hit_rate@k"] == 1.0
