"""Typed models used across the benchmark engine and UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, MutableMapping, Sequence


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    return value


@dataclass(frozen=True)
class Document:
    """A source document loaded into the benchmark."""

    doc_id: str
    content: str
    source: str = ""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Document":
        return cls(
            doc_id=_require_text(data["doc_id"], "doc_id"),
            content=_require_text(data["content"], "content"),
            source=_require_text(data.get("source", ""), "source"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Query:
    """A benchmark query."""

    query_id: str
    query: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Query":
        return cls(
            query_id=_require_text(data["query_id"], "query_id"),
            query=_require_text(data["query"], "query"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Chunk:
    """A chunk produced from a source document."""

    chunk_id: str
    doc_id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Chunk":
        metadata = data.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        return cls(
            chunk_id=_require_text(data["chunk_id"], "chunk_id"),
            doc_id=_require_text(data["doc_id"], "doc_id"),
            text=_require_text(data["text"], "text"),
            metadata=dict(metadata),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "text": self.text,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BenchmarkConfig:
    """User-selected benchmark configuration."""

    chunker_names: tuple[str, ...]
    embedder_names: tuple[str, ...]
    retriever_names: tuple[str, ...]
    top_k: int
    api_keys: Mapping[str, str] = field(default_factory=dict)
    credential_bindings: Mapping[str, str] = field(default_factory=dict)
    enable_disk_cache: bool = True
    persist_run_artifacts: bool = True

    @property
    def combination_count(self) -> int:
        return len(self.chunker_names) * len(self.embedder_names) * len(self.retriever_names)


@dataclass(frozen=True)
class BenchmarkRow:
    """One aggregate benchmark result row."""

    chunker: str
    embedder: str
    retriever: str
    precision_at_k: float
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    map_at_k: float
    hit_rate_at_k: float
    latency_ms: float
    num_chunks: int
    avg_chunk_size: float
    error: str = ""

    def to_mapping(self) -> dict[str, Any]:
        return {
            "chunker": self.chunker,
            "embedder": self.embedder,
            "retriever": self.retriever,
            "precision@k": self.precision_at_k,
            "recall@k": self.recall_at_k,
            "mrr": self.mrr,
            "ndcg@k": self.ndcg_at_k,
            "map@k": self.map_at_k,
            "hit_rate@k": self.hit_rate_at_k,
            "latency_ms": self.latency_ms,
            "num_chunks": self.num_chunks,
            "avg_chunk_size": self.avg_chunk_size,
            "error": self.error,
        }


@dataclass(frozen=True)
class BenchmarkArtifacts:
    """Saved artifact paths for a benchmark run."""

    run_id: str
    directory: str
    summary_json: str
    results_csv: str
    results_json: str
    per_query_json: str


def normalize_documents(documents: Sequence[Document | Mapping[str, Any]]) -> list[Document]:
    """Convert user-provided document mappings into typed documents."""
    normalized: list[Document] = []
    for document in documents:
        normalized.append(document if isinstance(document, Document) else Document.from_mapping(document))
    return normalized


def normalize_queries(queries: Sequence[Query | Mapping[str, Any]]) -> list[Query]:
    """Convert user-provided query mappings into typed queries."""
    normalized: list[Query] = []
    for query in queries:
        normalized.append(query if isinstance(query, Query) else Query.from_mapping(query))
    return normalized


def normalize_chunks(chunks: Sequence[Chunk | Mapping[str, Any]]) -> list[Chunk]:
    """Convert chunk mappings into typed chunks."""
    normalized: list[Chunk] = []
    for chunk in chunks:
        normalized.append(chunk if isinstance(chunk, Chunk) else Chunk.from_mapping(chunk))
    return normalized


def normalize_ground_truth(
    ground_truth: Mapping[str, Sequence[str] | set[str] | tuple[str, ...]],
) -> dict[str, set[str]]:
    """Normalize ground-truth mappings into sets."""
    normalized: dict[str, set[str]] = {}
    for query_id, relevant_doc_ids in ground_truth.items():
        if not isinstance(query_id, str):
            raise TypeError("query_id keys in ground_truth must be strings")
        normalized[query_id] = {str(doc_id) for doc_id in relevant_doc_ids}
    return normalized


def redact_api_keys(api_keys: Mapping[str, str]) -> dict[str, str]:
    """Return masked API-key values for safe metadata logging."""
    redacted: dict[str, str] = {}
    for name, value in api_keys.items():
        if not value:
            redacted[name] = ""
        elif len(value) <= 6:
            redacted[name] = "*" * len(value)
        else:
            redacted[name] = f"{value[:3]}...{value[-3:]}"
    return redacted
