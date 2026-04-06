"""Validation helpers for benchmark inputs."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping, Sequence

from rag_ops.models import Document, Query


class ValidationError(ValueError):
    """Raised when uploaded or in-memory benchmark data is invalid."""


def _find_duplicates(values: Iterable[str]) -> list[str]:
    counts = Counter(values)
    return sorted([value for value, count in counts.items() if count > 1])


def validate_documents(documents: Sequence[Document]) -> None:
    """Validate loaded documents."""
    if not documents:
        raise ValidationError("At least one document is required.")

    duplicate_ids = _find_duplicates(document.doc_id for document in documents)
    if duplicate_ids:
        raise ValidationError(f"Duplicate document IDs found: {', '.join(duplicate_ids)}")

    empty_ids = [document.doc_id for document in documents if not document.doc_id.strip()]
    if empty_ids:
        raise ValidationError("Document IDs cannot be empty.")

    empty_content = [document.doc_id for document in documents if not document.content.strip()]
    if empty_content:
        raise ValidationError(
            f"Documents must contain text. Empty content found in: {', '.join(empty_content)}"
        )


def validate_queries(
    queries: Sequence[Query],
    ground_truth: Mapping[str, set[str]],
    document_ids: Iterable[str],
) -> None:
    """Validate queries and their ground-truth mappings."""
    if not queries:
        raise ValidationError("At least one query is required.")

    duplicate_query_ids = _find_duplicates(query.query_id for query in queries)
    if duplicate_query_ids:
        raise ValidationError(f"Duplicate query IDs found: {', '.join(duplicate_query_ids)}")

    empty_queries = [query.query_id for query in queries if not query.query.strip()]
    if empty_queries:
        raise ValidationError(
            f"Queries must contain text. Empty query text found in: {', '.join(empty_queries)}"
        )

    document_id_set = set(document_ids)
    missing_ground_truth = [query.query_id for query in queries if query.query_id not in ground_truth]
    if missing_ground_truth:
        raise ValidationError(
            "Every query must have ground truth. Missing entries for: "
            + ", ".join(missing_ground_truth)
        )

    unknown_doc_refs: list[str] = []
    empty_relevance: list[str] = []
    for query in queries:
        relevant_doc_ids = ground_truth.get(query.query_id, set())
        if not relevant_doc_ids:
            empty_relevance.append(query.query_id)
            continue
        missing_ids = sorted(set(relevant_doc_ids) - document_id_set)
        if missing_ids:
            unknown_doc_refs.append(f"{query.query_id}: {', '.join(missing_ids)}")

    if empty_relevance:
        raise ValidationError(
            "Each query must reference at least one relevant document. Empty labels for: "
            + ", ".join(empty_relevance)
        )

    if unknown_doc_refs:
        raise ValidationError(
            "Ground truth references unknown document IDs. " + " | ".join(unknown_doc_refs)
        )


def validate_benchmark_configuration(
    chunker_names: Sequence[str],
    embedder_names: Sequence[str],
    retriever_names: Sequence[str],
    top_k: int,
) -> None:
    """Validate runtime configuration."""
    if not chunker_names:
        raise ValidationError("Select at least one chunking strategy.")
    if not embedder_names:
        raise ValidationError("Select at least one embedding model.")
    if not retriever_names:
        raise ValidationError("Select at least one retrieval method.")
    if top_k <= 0:
        raise ValidationError("top_k must be greater than zero.")

