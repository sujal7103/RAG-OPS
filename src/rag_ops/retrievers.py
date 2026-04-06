"""Retrieval methods: dense (vector), sparse (BM25), and hybrid."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence

import numpy as np


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def build_dense_index(corpus_embeddings: np.ndarray) -> dict[str, Any]:
    """Create a dense retrieval resource, preferring FAISS when available."""
    try:  # pragma: no cover - exercised when faiss is installed
        import faiss  # type: ignore

        dimension = corpus_embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(corpus_embeddings.astype(np.float32))
        return {"backend": "faiss", "index": index}
    except ImportError:
        return {"backend": "numpy", "embeddings": corpus_embeddings.astype(np.float32)}


def _search_dense_index(
    query_embedding: np.ndarray,
    corpus_embeddings: np.ndarray,
    top_k: int,
    dense_index: Mapping[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    resource = dense_index or build_dense_index(corpus_embeddings)

    if resource["backend"] == "faiss":  # pragma: no cover - depends on optional package
        query = query_embedding.reshape(1, -1).astype(np.float32)
        scores, indices = resource["index"].search(query, min(top_k, len(corpus_embeddings)))
        return scores[0], indices[0]

    embeddings = resource["embeddings"]
    query = query_embedding.astype(np.float32)
    scores = embeddings @ query
    limit = min(top_k, len(scores))
    top_indices = np.argsort(scores)[::-1][:limit]
    return scores[top_indices], top_indices


def dense_retrieve(
    query_embedding: np.ndarray,
    corpus_embeddings: np.ndarray,
    chunks: Sequence[Mapping[str, Any]],
    top_k: int,
    dense_index: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Vector similarity search using FAISS or a numpy fallback."""
    scores, indices = _search_dense_index(query_embedding, corpus_embeddings, top_k, dense_index)

    results: list[dict[str, Any]] = []
    for score, index in zip(scores, indices):
        if index < 0:
            continue
        chunk = chunks[int(index)]
        results.append(
            {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "score": float(score),
            }
        )
    return results


def _build_sparse_fallback_model(chunks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    tokenized_corpus = [_tokenize(chunk["text"]) for chunk in chunks]
    doc_freq = Counter()
    total_length = 0
    for tokens in tokenized_corpus:
        total_length += len(tokens)
        doc_freq.update(set(tokens))

    avg_doc_length = total_length / len(tokenized_corpus) if tokenized_corpus else 0.0
    doc_term_freqs = [Counter(tokens) for tokens in tokenized_corpus]
    return {
        "backend": "fallback",
        "tokenized_corpus": tokenized_corpus,
        "doc_term_freqs": doc_term_freqs,
        "doc_freq": doc_freq,
        "avg_doc_length": avg_doc_length,
        "num_docs": len(tokenized_corpus),
        "k1": 1.5,
        "b": 0.75,
    }


def build_sparse_index(chunks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Create a sparse retrieval resource, preferring rank-bm25 when available."""
    tokenized_corpus = [_tokenize(chunk["text"]) for chunk in chunks]
    try:  # pragma: no cover - depends on optional package
        from rank_bm25 import BM25Okapi  # type: ignore

        return {
            "backend": "rank_bm25",
            "tokenized_corpus": tokenized_corpus,
            "bm25": BM25Okapi(tokenized_corpus),
        }
    except ImportError:
        return _build_sparse_fallback_model(chunks)


def _score_sparse_fallback(query_tokens: Sequence[str], sparse_index: Mapping[str, Any]) -> np.ndarray:
    scores = []
    num_docs = sparse_index["num_docs"]
    avg_doc_length = sparse_index["avg_doc_length"] or 1.0
    k1 = sparse_index["k1"]
    b = sparse_index["b"]

    for doc_term_freqs, doc_tokens in zip(
        sparse_index["doc_term_freqs"], sparse_index["tokenized_corpus"]
    ):
        doc_length = len(doc_tokens) or 1
        score = 0.0
        for token in query_tokens:
            tf = doc_term_freqs.get(token, 0)
            if tf <= 0:
                continue
            df = sparse_index["doc_freq"].get(token, 0)
            idf = math.log(1 + (num_docs - df + 0.5) / (df + 0.5))
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))
            score += idf * numerator / denominator
        scores.append(score)
    return np.array(scores, dtype=np.float32)


def sparse_retrieve(
    query: str,
    chunks: Sequence[Mapping[str, Any]],
    top_k: int,
    sparse_index: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """BM25 keyword-based retrieval with a fallback implementation."""
    resource = sparse_index or build_sparse_index(chunks)
    query_tokens = _tokenize(query)

    if resource["backend"] == "rank_bm25":  # pragma: no cover - depends on optional package
        scores = np.array(resource["bm25"].get_scores(query_tokens), dtype=np.float32)
    else:
        scores = _score_sparse_fallback(query_tokens, resource)

    top_indices = np.argsort(scores)[::-1][:top_k]
    results: list[dict[str, Any]] = []
    for index in top_indices:
        if scores[index] <= 0:
            continue
        chunk = chunks[int(index)]
        results.append(
            {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "score": float(scores[index]),
            }
        )
    return results


def hybrid_retrieve(
    query: str,
    query_embedding: np.ndarray,
    corpus_embeddings: np.ndarray,
    chunks: Sequence[Mapping[str, Any]],
    top_k: int,
    dense_weight: float = 0.7,
    dense_index: Mapping[str, Any] | None = None,
    sparse_index: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Hybrid retrieval combining dense and sparse results using Reciprocal Rank Fusion."""
    rrf_k = 60
    fetch_k = min(top_k * 3, len(chunks))
    dense_results = dense_retrieve(
        query_embedding,
        corpus_embeddings,
        chunks,
        fetch_k,
        dense_index=dense_index,
    )
    sparse_results = sparse_retrieve(query, chunks, fetch_k, sparse_index=sparse_index)

    rrf_scores: dict[str, float] = {}
    for rank, result in enumerate(dense_results):
        chunk_id = result["chunk_id"]
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + dense_weight / (rrf_k + rank + 1)

    sparse_weight = 1.0 - dense_weight
    for rank, result in enumerate(sparse_results):
        chunk_id = result["chunk_id"]
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + sparse_weight / (rrf_k + rank + 1)

    chunk_map = {chunk["chunk_id"]: chunk for chunk in chunks}
    sorted_chunk_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
    return [
        {
            "chunk_id": chunk_id,
            "doc_id": chunk_map[chunk_id]["doc_id"],
            "score": rrf_scores[chunk_id],
        }
        for chunk_id in sorted_chunk_ids
    ]


RETRIEVERS = ["Dense", "Sparse", "Hybrid"]


def prepare_retriever_resources(
    retriever_names: Sequence[str],
    corpus_embeddings: np.ndarray,
    chunks: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Pre-build reusable retrieval resources for the selected retrievers."""
    resources: dict[str, dict[str, Any]] = {}
    if "Dense" in retriever_names or "Hybrid" in retriever_names:
        resources["dense"] = build_dense_index(corpus_embeddings)
    if "Sparse" in retriever_names or "Hybrid" in retriever_names:
        resources["sparse"] = build_sparse_index(chunks)
    return resources


def retrieve(
    query: str,
    query_embedding: np.ndarray,
    corpus_embeddings: np.ndarray,
    chunks: Sequence[Mapping[str, Any]],
    retriever_name: str,
    top_k: int,
    resources: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Run retrieval using the specified method."""
    resources = resources or {}
    if retriever_name == "Dense":
        return dense_retrieve(
            query_embedding,
            corpus_embeddings,
            chunks,
            top_k,
            dense_index=resources.get("dense"),
        )
    if retriever_name == "Sparse":
        return sparse_retrieve(query, chunks, top_k, sparse_index=resources.get("sparse"))
    if retriever_name == "Hybrid":
        return hybrid_retrieve(
            query,
            query_embedding,
            corpus_embeddings,
            chunks,
            top_k,
            dense_index=resources.get("dense"),
            sparse_index=resources.get("sparse"),
        )
    raise ValueError(f"Unknown retriever: {retriever_name}")

