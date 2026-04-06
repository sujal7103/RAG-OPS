"""Disk cache helpers for chunk and embedding reuse."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from rag_ops.models import Chunk, Document, Query

CACHE_VERSION = "v1"
DEFAULT_CACHE_DIRNAME = ".rag_ops_cache"


def get_cache_dir(cache_dir: str | Path | None = None) -> Path:
    """Resolve and create the cache directory."""
    configured = cache_dir or os.getenv("RAG_OPS_CACHE_DIR") or DEFAULT_CACHE_DIRNAME
    path = Path(configured)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stable_payload(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint_dataset(
    documents: Sequence[Document],
    queries: Sequence[Query],
    ground_truth: Mapping[str, set[str]],
) -> str:
    """Compute a stable fingerprint for the active benchmark dataset."""
    payload = {
        "documents": [
            {"doc_id": document.doc_id, "content": document.content, "source": document.source}
            for document in documents
        ],
        "queries": [
            {"query_id": query.query_id, "query": query.query}
            for query in queries
        ],
        "ground_truth": {query_id: sorted(doc_ids) for query_id, doc_ids in ground_truth.items()},
    }
    digest = hashlib.sha256(_stable_payload(payload).encode("utf-8")).hexdigest()
    return digest[:16]


def _component_key(dataset_fingerprint: str, *parts: str) -> str:
    digest = hashlib.sha256(
        _stable_payload([CACHE_VERSION, dataset_fingerprint, *parts]).encode("utf-8")
    ).hexdigest()
    return digest[:24]


def _chunks_path(cache_root: Path, dataset_fingerprint: str, chunker_name: str) -> Path:
    return cache_root / "chunks" / f"{_component_key(dataset_fingerprint, chunker_name)}.json"


def _embeddings_path(
    cache_root: Path,
    dataset_fingerprint: str,
    chunker_name: str,
    embedder_name: str,
) -> Path:
    return (
        cache_root
        / "embeddings"
        / f"{_component_key(dataset_fingerprint, chunker_name, embedder_name)}.npy"
    )


def load_cached_chunks(
    cache_root: Path,
    dataset_fingerprint: str,
    chunker_name: str,
) -> list[dict] | None:
    """Load cached chunks if present."""
    path = _chunks_path(cache_root, dataset_fingerprint, chunker_name)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_cached_chunks(
    cache_root: Path,
    dataset_fingerprint: str,
    chunker_name: str,
    chunks: Sequence[Mapping[str, object]],
) -> None:
    """Persist chunks to disk."""
    path = _chunks_path(cache_root, dataset_fingerprint, chunker_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(chunks), indent=2, sort_keys=True))


def load_cached_embeddings(
    cache_root: Path,
    dataset_fingerprint: str,
    chunker_name: str,
    embedder_name: str,
) -> np.ndarray | None:
    """Load cached corpus embeddings if present."""
    path = _embeddings_path(cache_root, dataset_fingerprint, chunker_name, embedder_name)
    if not path.exists():
        return None
    return np.load(path)


def save_cached_embeddings(
    cache_root: Path,
    dataset_fingerprint: str,
    chunker_name: str,
    embedder_name: str,
    embeddings: np.ndarray,
) -> None:
    """Persist corpus embeddings to disk."""
    path = _embeddings_path(cache_root, dataset_fingerprint, chunker_name, embedder_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, embeddings)

