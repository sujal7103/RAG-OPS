"""Tests for chunking strategies."""

from rag_ops.chunkers import (
    fixed_size_chunk,
    recursive_chunk,
    document_aware_chunk,
)


SAMPLE_TEXT = (
    "Python is a high-level programming language. "
    "It was created by Guido van Rossum. "
    "Python emphasizes code readability. "
    "It supports multiple paradigms including OOP and functional programming. "
    "The language has a comprehensive standard library."
)


def test_fixed_size_returns_chunks():
    chunks = fixed_size_chunk(SAMPLE_TEXT, "doc1", chunk_size=100, overlap=20)
    assert len(chunks) > 1
    for c in chunks:
        assert c["doc_id"] == "doc1"
        assert c["text"]
        assert c["chunk_id"].startswith("doc1::fixed_")


def test_fixed_size_respects_size():
    chunks = fixed_size_chunk(SAMPLE_TEXT, "doc1", chunk_size=100, overlap=0)
    for c in chunks:
        # Allow some slack for word boundary snapping
        assert len(c["text"]) <= 110


def test_fixed_size_empty_text():
    assert fixed_size_chunk("", "doc1") == []
    assert fixed_size_chunk("   ", "doc1") == []


def test_recursive_returns_chunks():
    chunks = recursive_chunk(SAMPLE_TEXT, "doc1", chunk_size=100, overlap=20)
    assert len(chunks) >= 1
    for c in chunks:
        assert c["doc_id"] == "doc1"
        assert c["chunk_id"].startswith("doc1::recursive_")


def test_recursive_short_text():
    chunks = recursive_chunk("Hello world", "doc1", chunk_size=500)
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Hello world"


def test_document_aware_with_headers():
    text = """# Introduction
This is the intro section with some content.

# Methods
We used several methods in this study.

## Method A
Method A is the first approach.

## Method B
Method B is the second approach.
"""
    chunks = document_aware_chunk(text, "doc1", max_size=500)
    assert len(chunks) >= 2
    for c in chunks:
        assert c["doc_id"] == "doc1"
        assert c["chunk_id"].startswith("doc1::docaware_")


def test_document_aware_no_headers():
    text = "Paragraph one about topic A.\n\nParagraph two about topic B.\n\nParagraph three."
    chunks = document_aware_chunk(text, "doc1")
    assert len(chunks) >= 1


def test_all_chunkers_produce_doc_id():
    """Every chunk must carry its parent doc_id."""
    for fn in [fixed_size_chunk, recursive_chunk, document_aware_chunk]:
        chunks = fn(SAMPLE_TEXT, "test_doc")
        for c in chunks:
            assert c["doc_id"] == "test_doc"
