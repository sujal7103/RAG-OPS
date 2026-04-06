"""Evaluation metrics for retrieval quality."""

import math


def precision_at_k(retrieved_doc_ids, relevant_doc_ids, k):
    """Fraction of retrieved documents (top-k) that are relevant."""
    top_k = retrieved_doc_ids[:k]
    if not top_k:
        return 0.0
    hits = len(set(top_k) & set(relevant_doc_ids))
    return hits / k


def recall_at_k(retrieved_doc_ids, relevant_doc_ids, k):
    """Fraction of relevant documents that appear in top-k results."""
    top_k = retrieved_doc_ids[:k]
    if not relevant_doc_ids:
        return 0.0
    hits = len(set(top_k) & set(relevant_doc_ids))
    return hits / len(relevant_doc_ids)


def mrr(retrieved_doc_ids, relevant_doc_ids):
    """Mean Reciprocal Rank — 1/rank of the first relevant result."""
    relevant_set = set(relevant_doc_ids)
    for i, doc_id in enumerate(retrieved_doc_ids):
        if doc_id in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved_doc_ids, relevant_doc_ids, k):
    """Normalized Discounted Cumulative Gain at k (binary relevance)."""
    relevant_set = set(relevant_doc_ids)
    top_k = retrieved_doc_ids[:k]

    # DCG
    dcg = sum(
        1.0 / math.log2(i + 2) for i, doc_id in enumerate(top_k)
        if doc_id in relevant_set
    )

    # Ideal DCG
    ideal_k = min(k, len(relevant_set))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_k))

    return dcg / idcg if idcg > 0 else 0.0


def map_at_k(retrieved_doc_ids, relevant_doc_ids, k):
    """Mean Average Precision at k."""
    relevant_set = set(relevant_doc_ids)
    top_k = retrieved_doc_ids[:k]

    hits = 0
    sum_precisions = 0.0
    for i, doc_id in enumerate(top_k):
        if doc_id in relevant_set:
            hits += 1
            sum_precisions += hits / (i + 1)

    return sum_precisions / len(relevant_set) if relevant_set else 0.0


def hit_rate_at_k(retrieved_doc_ids, relevant_doc_ids, k):
    """1 if any relevant document appears in top-k, else 0."""
    top_k = retrieved_doc_ids[:k]
    return 1.0 if set(top_k) & set(relevant_doc_ids) else 0.0


def evaluate_query(retrieved_doc_ids, relevant_doc_ids, k):
    """Compute all metrics for a single query. Returns a dict."""
    relevant_set = set(relevant_doc_ids)
    return {
        "precision@k": precision_at_k(retrieved_doc_ids, relevant_set, k),
        "recall@k": recall_at_k(retrieved_doc_ids, relevant_set, k),
        "mrr": mrr(retrieved_doc_ids, relevant_set),
        "ndcg@k": ndcg_at_k(retrieved_doc_ids, relevant_set, k),
        "map@k": map_at_k(retrieved_doc_ids, relevant_set, k),
        "hit_rate@k": hit_rate_at_k(retrieved_doc_ids, relevant_set, k),
    }
