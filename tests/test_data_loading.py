"""Tests for data loading and validation helpers."""

import pytest

from rag_ops.data_loading import load_uploaded_data
from rag_ops.validation import ValidationError


class FakeUpload:
    def __init__(self, name, payload):
        self.name = name
        self._payload = payload

    def read(self, size=-1):
        return self._payload


def test_load_uploaded_data_success():
    documents, queries, ground_truth = load_uploaded_data(
        [FakeUpload("doc_a.txt", b"hello world"), FakeUpload("doc_b.md", b"more text")],
        FakeUpload(
            "queries.json",
            b'[{"query_id":"q1","query":"hello?","relevant_doc_ids":["doc_a"]}]',
        ),
    )

    assert [document.doc_id for document in documents] == ["doc_a", "doc_b"]
    assert queries[0].query_id == "q1"
    assert ground_truth["q1"] == {"doc_a"}


def test_load_uploaded_data_rejects_duplicate_doc_ids():
    with pytest.raises(ValidationError):
        load_uploaded_data(
            [FakeUpload("doc_a.txt", b"hello"), FakeUpload("doc_a.md", b"again")],
            FakeUpload(
                "queries.json",
                b'[{"query_id":"q1","query":"hello?","relevant_doc_ids":["doc_a"]}]',
            ),
        )


def test_load_uploaded_data_rejects_unknown_ground_truth_ids():
    with pytest.raises(ValidationError):
        load_uploaded_data(
            [FakeUpload("doc_a.txt", b"hello")],
            FakeUpload(
                "queries.json",
                b'[{"query_id":"q1","query":"hello?","relevant_doc_ids":["missing_doc"]}]',
            ),
        )

