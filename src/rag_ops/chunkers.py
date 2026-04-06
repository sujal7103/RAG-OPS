"""Chunking strategies for splitting documents into smaller pieces."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from rag_ops.models import Document


def fixed_size_chunk(text, doc_id, chunk_size=512, overlap=64):
    """Split text into fixed-size character chunks with overlap.

    Snaps to word boundaries to avoid cutting words in half.
    """
    if not text.strip():
        return []

    chunks = []
    start = 0
    idx = 0

    while start < len(text):
        end = start + chunk_size

        # Snap to word boundary (don't cut words)
        if end < len(text):
            # Look for the last space before the end
            space_pos = text.rfind(" ", start, end)
            if space_pos > start:
                end = space_pos

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({
                "chunk_id": f"{doc_id}::fixed_{idx}",
                "doc_id": doc_id,
                "text": chunk_text,
                "metadata": {"chunker": "Fixed Size", "start": start, "end": end},
            })
            idx += 1

        start = end - overlap
        if start <= chunks[-1]["metadata"]["start"] if chunks else False:
            start = end  # prevent infinite loops

    return chunks


def recursive_chunk(text, doc_id, chunk_size=512, overlap=64):
    """Recursively split text using a hierarchy of separators.

    Tries paragraph breaks first, then newlines, then sentences, then spaces.
    """
    separators = ["\n\n", "\n", ". ", " "]

    def _split(text, sep_idx):
        if len(text) <= chunk_size or sep_idx >= len(separators):
            return [text] if text.strip() else []

        sep = separators[sep_idx]
        parts = text.split(sep)
        result = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    result.append(current)
                # If this single part is too big, recurse with next separator
                if len(part) > chunk_size:
                    result.extend(_split(part, sep_idx + 1))
                else:
                    current = part
                    continue
                current = ""

        if current.strip():
            result.append(current)

        return result

    pieces = _split(text, 0)

    # Apply overlap by including tail of previous chunk
    chunks = []
    for idx, piece in enumerate(pieces):
        chunk_text = piece.strip()
        if not chunk_text:
            continue

        # Add overlap from previous chunk
        if idx > 0 and overlap > 0 and len(pieces[idx - 1]) > overlap:
            prefix = pieces[idx - 1][-overlap:]
            # Snap to word boundary
            space_pos = prefix.find(" ")
            if space_pos >= 0:
                prefix = prefix[space_pos + 1:]
            chunk_text = prefix + " " + chunk_text

        chunks.append({
            "chunk_id": f"{doc_id}::recursive_{idx}",
            "doc_id": doc_id,
            "text": chunk_text,
            "metadata": {"chunker": "Recursive"},
        })

    return chunks


def semantic_chunk(text, doc_id, threshold=0.5):
    """Split text into chunks based on semantic similarity between sentences.

    Groups consecutive sentences that are semantically similar.
    Uses sentence-transformers for encoding.
    """
    import numpy as np

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 1:
        return [{
            "chunk_id": f"{doc_id}::semantic_0",
            "doc_id": doc_id,
            "text": text.strip(),
            "metadata": {"chunker": "Semantic"},
        }]

    # Encode sentences
    model = _get_semantic_model()
    embeddings = model.encode(sentences, show_progress_bar=False)

    # Compute cosine similarity between adjacent sentences
    similarities = []
    for i in range(len(embeddings) - 1):
        sim = np.dot(embeddings[i], embeddings[i + 1]) / (
            np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i + 1]) + 1e-8
        )
        similarities.append(sim)

    # Find split points where similarity drops below threshold
    split_indices = [0]
    for i, sim in enumerate(similarities):
        if sim < threshold:
            split_indices.append(i + 1)
    split_indices.append(len(sentences))

    # Build chunks from sentence groups
    chunks = []
    for idx in range(len(split_indices) - 1):
        start = split_indices[idx]
        end = split_indices[idx + 1]
        chunk_text = " ".join(sentences[start:end]).strip()
        if chunk_text:
            chunks.append({
                "chunk_id": f"{doc_id}::semantic_{idx}",
                "doc_id": doc_id,
                "text": chunk_text,
                "metadata": {"chunker": "Semantic"},
            })

    return chunks


def document_aware_chunk(text, doc_id, max_size=1500):
    """Split text respecting document structure (headings, code blocks, paragraphs).

    Recognizes markdown headers and code fences, keeping sections intact.
    """
    sections = []
    current_header = ""
    current_content = []
    in_code_block = False

    for line in text.split("\n"):
        # Track code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            current_content.append(line)
            continue

        # Don't split inside code blocks
        if in_code_block:
            current_content.append(line)
            continue

        # Check for headers
        header_match = re.match(r'^(#{1,6})\s+(.+)', line)
        if header_match:
            # Save previous section
            if current_content:
                content = "\n".join(current_content).strip()
                if content:
                    sections.append({"header": current_header, "content": content})
            current_header = line.strip()
            current_content = []
        else:
            current_content.append(line)

    # Don't forget the last section
    if current_content:
        content = "\n".join(current_content).strip()
        if content:
            sections.append({"header": current_header, "content": content})

    # If no headers found, split by double newlines (paragraphs)
    if not sections:
        paragraphs = text.split("\n\n")
        sections = [{"header": "", "content": p.strip()} for p in paragraphs if p.strip()]

    # Build chunks, splitting oversized sections
    chunks = []
    idx = 0
    for section in sections:
        content = section["content"]
        header = section["header"]

        if len(content) <= max_size:
            chunk_text = f"{header}\n{content}".strip() if header else content
            chunks.append({
                "chunk_id": f"{doc_id}::docaware_{idx}",
                "doc_id": doc_id,
                "text": chunk_text,
                "metadata": {"chunker": "Document-Aware", "header": header},
            })
            idx += 1
        else:
            # Sub-chunk oversized sections by paragraphs
            paragraphs = content.split("\n\n")
            current_chunk = header + "\n" if header else ""

            for para in paragraphs:
                if len(current_chunk) + len(para) > max_size and current_chunk.strip():
                    chunks.append({
                        "chunk_id": f"{doc_id}::docaware_{idx}",
                        "doc_id": doc_id,
                        "text": current_chunk.strip(),
                        "metadata": {"chunker": "Document-Aware", "header": header},
                    })
                    idx += 1
                    current_chunk = ""
                current_chunk += para + "\n\n"

            if current_chunk.strip():
                chunks.append({
                    "chunk_id": f"{doc_id}::docaware_{idx}",
                    "doc_id": doc_id,
                    "text": current_chunk.strip(),
                    "metadata": {"chunker": "Document-Aware", "header": header},
                })
                idx += 1

    return chunks


# ── Helpers ─────────────────────────────────────────────────────────────────

_semantic_model = None


def _get_semantic_model():
    """Lazy-load the sentence-transformers model (cached)."""
    global _semantic_model
    if _semantic_model is None:
        from sentence_transformers import SentenceTransformer
        _semantic_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _semantic_model


# ── Dispatcher ──────────────────────────────────────────────────────────────

CHUNKERS = {
    "Fixed Size": fixed_size_chunk,
    "Recursive": recursive_chunk,
    "Semantic": semantic_chunk,
    "Document-Aware": document_aware_chunk,
}


def chunk_documents(documents: Sequence[Document | Mapping[str, Any]], chunker_name):
    """Chunk all documents using the specified strategy. Returns list of chunk dicts."""
    fn = CHUNKERS[chunker_name]
    all_chunks = []
    for doc in documents:
        if isinstance(doc, Document):
            all_chunks.extend(fn(doc.content, doc.doc_id))
        else:
            all_chunks.extend(fn(doc["content"], doc["doc_id"]))
    return all_chunks
