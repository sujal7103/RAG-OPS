"""Data loading and validation helpers for sample and uploaded datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, Sequence

from rag_ops.models import Document, Query, normalize_ground_truth
from rag_ops.validation import validate_documents, validate_queries


class UploadedFileLike(Protocol):
    """Protocol for Streamlit-style uploaded files."""

    name: str

    def read(self, size: int = -1) -> bytes:
        """Return file contents as bytes."""


SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"


def _decode_bytes(raw: bytes, source_name: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _parse_queries_payload(raw_text: str) -> tuple[list[Query], dict[str, set[str]]]:
    try:
        queries_data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"queries.json is not valid JSON: {exc}") from exc

    if not isinstance(queries_data, list):
        raise ValueError("queries.json must contain a list of query objects.")

    queries: list[Query] = []
    ground_truth_raw: dict[str, Sequence[str]] = {}

    for index, item in enumerate(queries_data):
        if not isinstance(item, dict):
            raise ValueError(f"Query item at index {index} must be an object.")

        missing_fields = [
            field_name
            for field_name in ("query_id", "query", "relevant_doc_ids")
            if field_name not in item
        ]
        if missing_fields:
            raise ValueError(
                f"Query item at index {index} is missing fields: {', '.join(missing_fields)}"
            )

        relevant_doc_ids = item["relevant_doc_ids"]
        if not isinstance(relevant_doc_ids, list):
            raise ValueError(
                f"relevant_doc_ids for query {item['query_id']} must be a list of document IDs."
            )

        query = Query.from_mapping(item)
        queries.append(query)
        ground_truth_raw[query.query_id] = [str(doc_id) for doc_id in relevant_doc_ids]

    return queries, normalize_ground_truth(ground_truth_raw)


def load_sample_data(sample_data_dir: Path = SAMPLE_DATA_DIR) -> tuple[list[Document], list[Query], dict[str, set[str]]]:
    """Load the built-in sample documents and queries."""
    corpus_dir = sample_data_dir / "corpus"
    documents = [
        Document(doc_id=file_path.stem, content=file_path.read_text(), source=file_path.name)
        for file_path in sorted(corpus_dir.glob("*.txt"))
    ]

    queries, ground_truth = _parse_queries_payload((sample_data_dir / "queries.json").read_text())

    validate_documents(documents)
    validate_queries(queries, ground_truth, [document.doc_id for document in documents])
    return documents, queries, ground_truth


def load_local_data(
    document_paths: Sequence[str | Path],
    queries_path: str | Path,
) -> tuple[list[Document], list[Query], dict[str, set[str]]]:
    """Load documents and queries from local filesystem paths."""
    documents = [
        Document(
            doc_id=Path(file_path).stem,
            content=Path(file_path).read_text(),
            source=Path(file_path).name,
        )
        for file_path in document_paths
    ]
    queries, ground_truth = _parse_queries_payload(Path(queries_path).read_text())
    validate_documents(documents)
    validate_queries(queries, ground_truth, [document.doc_id for document in documents])
    return documents, queries, ground_truth


def load_uploaded_data(
    doc_files: Sequence[UploadedFileLike],
    queries_file: UploadedFileLike,
) -> tuple[list[Document], list[Query], dict[str, set[str]]]:
    """Load user-uploaded documents and a queries JSON file."""
    documents: list[Document] = []
    for file_obj in doc_files:
        doc_id = Path(file_obj.name).stem.strip()
        content = _decode_bytes(file_obj.read(), file_obj.name)
        documents.append(Document(doc_id=doc_id, content=content, source=file_obj.name))

    queries_raw = _decode_bytes(queries_file.read(), queries_file.name)
    queries, ground_truth = _parse_queries_payload(queries_raw)

    validate_documents(documents)
    validate_queries(queries, ground_truth, [document.doc_id for document in documents])
    return documents, queries, ground_truth
