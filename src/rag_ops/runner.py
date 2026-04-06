"""Benchmark runner — orchestrates chunking, embedding, retrieval, and evaluation."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from rag_ops.cache import (
    fingerprint_dataset,
    get_cache_dir,
    load_cached_chunks,
    load_cached_embeddings,
    save_cached_chunks,
    save_cached_embeddings,
)
from rag_ops.chunkers import chunk_documents
from rag_ops.embedders import embed_texts
from rag_ops.experiment_store import persist_benchmark_run
from rag_ops.metrics import evaluate_query
from rag_ops.models import (
    BenchmarkRow,
    normalize_documents,
    normalize_ground_truth,
    normalize_queries,
    redact_api_keys,
)
from rag_ops.results_frame import build_results_frame
from rag_ops.retrievers import prepare_retriever_resources, retrieve
from rag_ops.validation import (
    validate_benchmark_configuration,
    validate_documents,
    validate_queries,
)


def _chunk_stats(chunks: Sequence[Mapping[str, Any]]) -> tuple[int, float]:
    if not chunks:
        return 0, 0.0
    sizes = [len(chunk["text"]) for chunk in chunks]
    return len(chunks), float(np.mean(sizes))


def _finalize_row(
    chunker_name: str,
    embedder_name: str,
    retriever_name: str,
    num_chunks: int,
    avg_chunk_size: float,
    *,
    metrics: Mapping[str, float] | None = None,
    latency_ms: float = 0.0,
    error: str = "",
) -> dict[str, Any]:
    metrics = metrics or {
        "precision@k": 0.0,
        "recall@k": 0.0,
        "mrr": 0.0,
        "ndcg@k": 0.0,
        "map@k": 0.0,
        "hit_rate@k": 0.0,
    }
    return BenchmarkRow(
        chunker=chunker_name,
        embedder=embedder_name,
        retriever=retriever_name,
        precision_at_k=metrics["precision@k"],
        recall_at_k=metrics["recall@k"],
        mrr=metrics["mrr"],
        ndcg_at_k=metrics["ndcg@k"],
        map_at_k=metrics["map@k"],
        hit_rate_at_k=metrics["hit_rate@k"],
        latency_ms=latency_ms,
        num_chunks=num_chunks,
        avg_chunk_size=avg_chunk_size,
        error=error,
    ).to_mapping()


def run_benchmark(
    documents,
    queries,
    ground_truth,
    chunker_names,
    embedder_names,
    retriever_names,
    top_k,
    api_keys=None,
    progress_callback=None,
    enable_disk_cache: bool = False,
    cache_dir: str | None = None,
    persist_run_artifacts: bool = False,
    runs_dir: str | None = None,
    artifact_callback: Callable[[Any], None] | None = None,
):
    """Run the full benchmark across all combinations."""
    api_keys = api_keys or {}
    typed_documents = normalize_documents(documents)
    typed_queries = normalize_queries(queries)
    normalized_ground_truth = normalize_ground_truth(ground_truth)

    validate_documents(typed_documents)
    validate_queries(
        typed_queries,
        normalized_ground_truth,
        [document.doc_id for document in typed_documents],
    )
    validate_benchmark_configuration(chunker_names, embedder_names, retriever_names, top_k)

    dataset_fingerprint = fingerprint_dataset(
        typed_documents,
        typed_queries,
        normalized_ground_truth,
    )
    cache_root = get_cache_dir(cache_dir) if enable_disk_cache else None

    results: list[dict[str, Any]] = []
    per_query_results: dict[str, list[dict[str, Any]]] = {}

    total_combos = len(chunker_names) * len(embedder_names) * len(retriever_names)
    completed = 0

    def report(message: str) -> None:
        if progress_callback:
            pct = int((completed / total_combos) * 100) if total_combos > 0 else 0
            progress_callback(min(pct, 99), message)

    for chunker_name in chunker_names:
        report(f"Chunking documents with {chunker_name}...")

        chunks = (
            load_cached_chunks(cache_root, dataset_fingerprint, chunker_name)
            if cache_root is not None
            else None
        )
        if chunks is None:
            chunks = chunk_documents(typed_documents, chunker_name)
            if cache_root is not None:
                save_cached_chunks(cache_root, dataset_fingerprint, chunker_name, chunks)

        num_chunks, avg_chunk_size = _chunk_stats(chunks)
        if not chunks:
            for embedder_name in embedder_names:
                for retriever_name in retriever_names:
                    results.append(
                        _finalize_row(
                            chunker_name,
                            embedder_name,
                            retriever_name,
                            num_chunks,
                            avg_chunk_size,
                            error="No chunks were produced for the selected documents.",
                        )
                    )
                    completed += 1
            continue

        chunk_texts = [chunk["text"] for chunk in chunks]

        for embedder_name in embedder_names:
            report(f"Preparing corpus embeddings with {embedder_name}...")

            corpus_embeddings = (
                load_cached_embeddings(cache_root, dataset_fingerprint, chunker_name, embedder_name)
                if cache_root is not None
                else None
            )

            try:
                if corpus_embeddings is None:
                    corpus_embeddings = embed_texts(
                        chunk_texts,
                        embedder_name,
                        api_keys,
                        is_query=False,
                    )
                    if cache_root is not None:
                        save_cached_embeddings(
                            cache_root,
                            dataset_fingerprint,
                            chunker_name,
                            embedder_name,
                            corpus_embeddings,
                        )
            except Exception as exc:
                for retriever_name in retriever_names:
                    results.append(
                        _finalize_row(
                            chunker_name,
                            embedder_name,
                            retriever_name,
                            num_chunks,
                            avg_chunk_size,
                            error=str(exc),
                        )
                    )
                    completed += 1
                continue

            query_embedding_cache: dict[str, np.ndarray] = {}
            retriever_resources = prepare_retriever_resources(retriever_names, corpus_embeddings, chunks)

            for retriever_name in retriever_names:
                report(f"Retrieving with {retriever_name} ({chunker_name} + {embedder_name})...")
                label = f"{chunker_name} + {embedder_name} + {retriever_name}"
                query_metrics: list[dict[str, float]] = []
                query_details: list[dict[str, Any]] = []
                total_latency = 0.0

                try:
                    for query in typed_queries:
                        relevant = normalized_ground_truth.get(query.query_id, set())

                        if query.query_id not in query_embedding_cache:
                            query_embedding_cache[query.query_id] = embed_texts(
                                [query.query],
                                embedder_name,
                                api_keys,
                                is_query=True,
                            )[0]
                        query_embedding = query_embedding_cache[query.query_id]

                        start_time = time.perf_counter()
                        retrieved = retrieve(
                            query.query,
                            query_embedding,
                            corpus_embeddings,
                            chunks,
                            retriever_name,
                            top_k,
                            resources=retriever_resources,
                        )
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        total_latency += elapsed_ms

                        seen_doc_ids: set[str] = set()
                        retrieved_doc_ids: list[str] = []
                        for result in retrieved:
                            doc_id = result["doc_id"]
                            if doc_id not in seen_doc_ids:
                                seen_doc_ids.add(doc_id)
                                retrieved_doc_ids.append(doc_id)

                        scores = evaluate_query(retrieved_doc_ids, relevant, top_k)
                        query_metrics.append(scores)
                        query_details.append(
                            {
                                "query_id": query.query_id,
                                "query": query.query,
                                "retrieved_docs": ", ".join(retrieved_doc_ids[:top_k]),
                                "relevant_docs": ", ".join(sorted(relevant)),
                                "hit": bool(set(retrieved_doc_ids[:top_k]) & relevant),
                                "precision": scores["precision@k"],
                                "recall": scores["recall@k"],
                                "mrr": scores["mrr"],
                            }
                        )
                except Exception as exc:
                    results.append(
                        _finalize_row(
                            chunker_name,
                            embedder_name,
                            retriever_name,
                            num_chunks,
                            avg_chunk_size,
                            error=str(exc),
                        )
                    )
                    completed += 1
                    continue

                avg_metrics = {
                    key: float(np.mean([metric_row[key] for metric_row in query_metrics]))
                    for key in query_metrics[0]
                }
                results.append(
                    _finalize_row(
                        chunker_name,
                        embedder_name,
                        retriever_name,
                        num_chunks,
                        avg_chunk_size,
                        metrics=avg_metrics,
                        latency_ms=(total_latency / len(typed_queries)) if typed_queries else 0.0,
                    )
                )
                per_query_results[label] = query_details
                completed += 1

    report("Done!")

    result_frame = build_results_frame(results)
    if not result_frame.empty:
        result_frame = result_frame.sort_values("recall@k", ascending=False).reset_index(drop=True)

    if persist_run_artifacts and results:
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        artifact = persist_benchmark_run(
            results_rows=results,
            per_query_results=per_query_results,
            metadata={
                "run_id": run_id,
                "dataset_fingerprint": dataset_fingerprint,
                "chunkers": list(chunker_names),
                "embedders": list(embedder_names),
                "retrievers": list(retriever_names),
                "top_k": top_k,
                "document_count": len(typed_documents),
                "query_count": len(typed_queries),
                "api_keys": redact_api_keys(api_keys),
            },
            runs_dir=runs_dir,
        )
        if artifact_callback:
            artifact_callback(artifact)

    return result_frame, per_query_results
