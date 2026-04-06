# Contributing to RAG-OPS

Thanks for your interest in contributing! RAG-OPS is a focused tool with clean extension points — whether you want to add a new chunker, a new embedding model, a metric, or improve the UI, there's a clear place to do it.

---

## Table of Contents

1. [Ways to contribute](#1-ways-to-contribute)
2. [Getting started](#2-getting-started)
3. [Project structure](#3-project-structure)
4. [Adding new components](#4-adding-new-components)
5. [Code style](#5-code-style)
6. [Testing](#6-testing)
7. [Submitting a pull request](#7-submitting-a-pull-request)
8. [Reporting bugs](#8-reporting-bugs)
9. [Suggesting features](#9-suggesting-features)

---

## 1. Ways to contribute

**High-impact areas we'd love help with:**

- **New chunking strategies** — sentence-window, parent-document, late chunking, agentic chunking
- **New embedding models** — Voyage AI, Mistral Embed, Jina, local Ollama models
- **New retrieval methods** — ColBERT, re-ranking (cross-encoders), MMR diversification
- **New metrics** — ROUGE overlap, context precision/recall (RAGAS-style)
- **Performance** — disk-cached embeddings, async API calls, streaming progress
- **UI improvements** — side-by-side query drill-down, configuration diffing, export to PDF
- **Documentation** — tutorials, worked examples, integration guides
- **Tests** — coverage for edge cases, integration tests with real API mocks

Not sure where to start? Look for issues labeled `good first issue`.

---

## 2. Getting started

### Fork and clone

```bash
git clone https://github.com/sausi-7/rag-ops.git
cd rag-ops
```

### Set up the dev environment

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The `[dev]` extra installs `pytest`, `pytest-cov`, and `ruff` (linter/formatter).

### Verify the setup

```bash
# Run the test suite
pytest

# Launch the app
streamlit run app.py
```

If both work, you're ready to develop.

---

## 3. Project structure

```
rag-ops/
├── app.py                          # Streamlit UI — sidebar config, results rendering
├── src/rag_ops/
│   ├── chunkers.py                 # Chunking strategies (add new ones here)
│   ├── embedders.py                # Embedding models (add new ones here)
│   ├── retrievers.py               # Retrieval methods (add new ones here)
│   ├── metrics.py                  # Evaluation metrics (add new ones here)
│   ├── runner.py                   # Orchestration — wires everything together
│   └── sample_data/
│       ├── corpus/                 # .txt documents for the built-in demo
│       └── queries.json            # Queries with ground-truth labels
└── tests/
    ├── test_chunkers.py
    ├── test_embedders.py
    ├── test_retrievers.py
    ├── test_metrics.py
    └── test_runner.py
```

For a full technical reference, see [README_TECHNICAL.md](README_TECHNICAL.md).

---

## 4. Adding new components

Each component type has a simple interface. Register your implementation in the relevant dict/list and add a checkbox to the sidebar in `app.py`.

### New chunking strategy

```python
# src/rag_ops/chunkers.py

def my_chunker(documents: list[dict]) -> list[dict]:
    """
    Args:
        documents: [{"doc_id": str, "content": str, "source": str}]
    Returns:
        [{"chunk_id": str, "doc_id": str, "text": str, "metadata": dict}]
    """
    chunks = []
    for doc in documents:
        # your logic
        chunks.append({
            "chunk_id": f"{doc['doc_id']}::mychunker_{i}",
            "doc_id": doc["doc_id"],
            "text": chunk_text,
            "metadata": {},
        })
    return chunks

# Register it:
CHUNKERS = {
    "Fixed Size": fixed_size_chunk,
    "Recursive": recursive_chunk,
    "Semantic": semantic_chunk,
    "Document-Aware": document_aware_chunk,
    "My Chunker": my_chunker,       # ← add here
}
```

Then add a checkbox in `app.py` (the sidebar chunking section) and append the name to `chunker_names`.

### New embedding model

```python
# src/rag_ops/embedders.py

def embed_mymodel(texts: list[str], api_keys: dict, is_query: bool) -> np.ndarray:
    """
    Args:
        texts:    list of strings to embed
        api_keys: dict of API keys {"openai": ..., "cohere": ..., "myservice": ...}
        is_query: True when embedding queries, False for corpus chunks
    Returns:
        float32 ndarray shape (len(texts), D), L2-normalized
    """
    # your embedding logic
    embeddings = ...

    # Always normalize
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return (embeddings / np.maximum(norms, 1e-9)).astype(np.float32)

EMBEDDERS = {
    ...
    "My Model": embed_mymodel,
}
```

If your model requires an API key, add a conditional `st.text_input` block in `app.py` (following the OpenAI/Cohere pattern) and pass the key through `api_keys`.

### New retrieval method

```python
# src/rag_ops/retrievers.py

def my_retrieve(
    query: str,
    query_embedding: np.ndarray,      # shape (D,), L2-normalized
    corpus_embeddings: np.ndarray,    # shape (N, D), L2-normalized
    chunks: list[dict],
    top_k: int,
) -> list[dict]:
    """Returns top_k chunks ordered by relevance score (descending)."""
    ...

RETRIEVERS = ["Dense", "Sparse", "Hybrid", "My Method"]
# also add the dispatch in the retrieve() function
```

### New metric

```python
# src/rag_ops/metrics.py

def my_metric(retrieved_doc_ids: list[str], relevant_doc_ids: set[str], k: int) -> float:
    ...

def evaluate_query(retrieved_doc_ids, relevant_doc_ids, k):
    return {
        ...
        "my_metric@k": my_metric(retrieved_doc_ids, relevant_doc_ids, k),
    }
```

The new key will automatically appear in the leaderboard and be available in heatmap/chart dropdowns.

---

## 5. Code style

We use **ruff** for linting and formatting:

```bash
# Check
ruff check src/ tests/

# Auto-fix
ruff check --fix src/ tests/

# Format
ruff format src/ tests/
```

Key conventions:
- Type hints on all public function signatures
- Docstrings on public functions (one-line summary is sufficient)
- No global mutable state except model caches (which are intentional)
- Keep each module focused — don't add retrieval logic to chunkers.py, etc.
- Prefer explicit over clever

---

## 6. Testing

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=rag_ops --cov-report=term-missing

# Run a specific test file
pytest tests/test_chunkers.py -v
```

**What to test:**

- Chunkers: chunk count, chunk_id format, no empty chunks, overlap behavior
- Embedders: output shape `(N, D)`, L2-normalized (norm ≈ 1.0), handles empty input
- Retrievers: returns ≤ top_k results, ordered by score, handles query with no matches
- Metrics: boundary cases (k=0, no relevant docs, all relevant docs retrieved)

For embedders that call external APIs, mock the API client:

```python
from unittest.mock import patch, MagicMock

def test_embed_openai():
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
    with patch("rag_ops.embedders.openai.OpenAI") as mock_client:
        mock_client.return_value.embeddings.create.return_value = mock_response
        result = embed_texts(["test"], "OpenAI Small", {"openai": "sk-test"})
    assert result.shape == (1, 1536)
```

---

## 7. Submitting a pull request

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-chunker
   ```

2. **Make your changes**, following the code style guidelines.

3. **Add tests** for any new functionality.

4. **Run the full test suite** and confirm it passes:
   ```bash
   pytest
   ruff check src/ tests/
   ```

5. **Write a clear PR description** covering:
   - What the change does
   - Why it's useful
   - How to test it manually (if applicable)
   - Any trade-offs or known limitations

6. **Keep PRs focused** — one feature or fix per PR. Large refactors should be discussed in an issue first.

### PR checklist

- [ ] Tests added for new functionality
- [ ] `pytest` passes
- [ ] `ruff check` passes with no errors
- [ ] New component registered in the relevant `CHUNKERS`/`EMBEDDERS`/`RETRIEVERS` dict
- [ ] Sidebar checkbox added in `app.py` (for new pipeline components)
- [ ] README_TECHNICAL.md updated if architecture changed

---

## 8. Reporting bugs

Please open a GitHub issue with:

- **What you expected** to happen
- **What actually happened** (include the full error message / traceback)
- **Steps to reproduce** (minimal example)
- **Environment**: Python version, OS, which embedding model you were using

---

## 9. Suggesting features

Open a GitHub issue with the `enhancement` label. Describe:
- The problem you're trying to solve (not just the solution)
- How it fits into the existing workflow
- Any prior art or references (papers, other tools)

For large features (new module, significant UI overhaul), it's worth discussing in an issue before opening a PR — this avoids duplicated effort and architectural mismatches.

---

Thanks for contributing. Every improvement — even a documentation fix — makes the tool better for everyone building RAG systems.
