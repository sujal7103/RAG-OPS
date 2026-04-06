# RAG-OPS — Technical Architecture

This document covers the internal architecture, design decisions, data flow, and extension points for RAG-OPS. For the user-facing overview, see [README.md](README.md).

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Pipeline Data Flow](#2-pipeline-data-flow)
3. [Module Reference](#3-module-reference)
   - [Chunkers](#31-chunkers-chunkerspy)
   - [Embedders](#32-embedders-embedderspy)
   - [Retrievers](#33-retrievers-retrieverspy)
   - [Metrics](#34-metrics-metricspy)
   - [Runner](#35-runner-runnerpy)
4. [Evaluation Design](#4-evaluation-design)
5. [Performance Characteristics](#5-performance-characteristics)
6. [Extension Guide](#6-extension-guide)
7. [Testing](#7-testing)
8. [Dependency Map](#8-dependency-map)

---

## 1. System Overview

RAG-OPS is structured as a pure evaluation harness — it does not generate LLM responses. It evaluates only the **retrieval** stage of a RAG pipeline: given a query, how well does the pipeline surface the right source documents?

The system has five independent layers:

```
┌──────────────────────────────────────────────────────┐
│                    Streamlit UI (app.py)              │
├──────────────────────────────────────────────────────┤
│                  Runner (runner.py)                   │  ← orchestration
├───────────┬───────────┬────────────┬──────────────────┤
│ Chunkers  │ Embedders │ Retrievers │    Metrics       │  ← pipeline stages
│(chunkers) │(embedders)│(retrievers)│  (metrics.py)    │
└───────────┴───────────┴────────────┴──────────────────┘
```

Each layer is **stateless and independently testable**. The runner wires them together and manages state (cached embeddings, progress callbacks, result accumulation).

---

## 2. Pipeline Data Flow

### Input types

```python
documents: list[dict]   # [{"doc_id": str, "content": str, "source": str}]
queries:   list[dict]   # [{"query_id": str, "query": str}]
ground_truth: dict      # {query_id: set[doc_id]}
```

### Execution graph

```
documents
    │
    ▼
[CHUNKER]  chunk(documents) → chunks
    │       list[{"chunk_id", "doc_id", "text", "metadata"}]
    │
    ▼
[EMBEDDER] embed_texts(chunk_texts) → corpus_embeddings
    │       ndarray shape (N, D)  — L2-normalized
    │
    ├─────────────────────────────────┐
    │                                 │
    ▼                                 ▼
[EMBEDDER] embed_texts([query])   [RETRIEVER]
    │       ndarray shape (1, D)       │
    │                                 │
    └──────────────────────────────── ▼
                              retrieve(query_emb, corpus_emb, chunks, top_k)
                                    │
                                    ▼ retrieved_chunks (ordered list)
                                    │
                              deduplicate doc_ids (preserve rank order)
                                    │
                                    ▼
                              [METRICS] evaluate_query(retrieved_doc_ids,
                                                        relevant_doc_ids, k)
                                    │
                                    ▼
                              {precision@k, recall@k, mrr,
                               ndcg@k, map@k, hit_rate@k}
```

### Output types

```python
results_df: pd.DataFrame
# columns: chunker, embedder, retriever, precision@k, recall@k, mrr,
#          ndcg@k, map@k, hit_rate@k, latency_ms, num_chunks,
#          avg_chunk_size, error

per_query_results: dict[str, list[dict]]
# key: "chunker / embedder / retriever"
# value: [{"query_id", "query", "retrieved_docs", "relevant_docs",
#           "hit", "recall@k", "mrr", ...}, ...]
```

---

## 3. Module Reference

### 3.1 Chunkers (`chunkers.py`)

All chunkers share the same interface:

```python
def chunk(documents: list[dict]) -> list[dict]:
    # returns: [{"chunk_id": str, "doc_id": str, "text": str, "metadata": dict}]
```

Registered in the `CHUNKERS` dict — keys are display names used by the UI and runner.

#### Fixed Size (`fixed_size_chunk`)

Splits document text into segments of `chunk_size=512` characters with `overlap=64` characters. Word-boundary snapping prevents cuts mid-word.

```
"...word boundary snap..."
 ├──────── 512 ────────┤
              ├── 64 ──┤──────── 512 ──────────┤
```

Best for: uniform corpora, baseline comparison. Fast, predictable chunk counts.

#### Recursive (`recursive_chunk`)

Hierarchical splitting with a separator waterfall: `"\n\n"` → `"\n"` → `". "` → `" "`. If a segment still exceeds `chunk_size`, it recurses with the next separator. Applies overlap from the tail of the previous chunk.

Best for: general prose, documentation. Preserves semantic units (paragraphs, sentences) better than fixed-size.

#### Semantic (`semantic_chunk`)

Uses `sentence-transformers/all-MiniLM-L6-v2` to embed individual sentences, then computes cosine similarity between adjacent sentences. A new chunk starts when similarity drops below `threshold=0.5`.

```python
# similarity between sentence i and sentence i+1
sim = np.dot(emb[i], emb[i+1])  # embeddings are L2-normalized
if sim < 0.5:
    start_new_chunk()
```

Model is lazily loaded and **cached globally** (`_semantic_model` module-level variable) to avoid repeated loading across combinations.

Best for: heterogeneous documents where topic shifts mid-document. Higher latency than fixed/recursive.

#### Document-Aware (`document_aware_chunk`)

Respects markdown structure. Detects:
- Headings (`# H1` through `###### H6`) — triggers a new chunk
- Fenced code blocks (` ``` `) — kept intact as a single chunk unit

Max chunk size: `1500` characters. Oversized sections are sub-chunked by paragraph.

Best for: markdown documentation, READMEs, structured technical content.

---

### 3.2 Embedders (`embedders.py`)

All embedders share the same interface:

```python
def embed(texts: list[str], api_keys: dict, is_query: bool) -> np.ndarray:
    # returns: float32 ndarray shape (len(texts), D), L2-normalized
```

Registered in the `EMBEDDERS` dict.

#### Local models (MiniLM, BGE Small)

Both use `sentence_transformers.SentenceTransformer`. Models are **lazily loaded and cached** in module-level dicts (`_local_models`).

| Model | HuggingFace ID | Dimensions | Notes |
|-------|---------------|------------|-------|
| MiniLM | `all-MiniLM-L6-v2` | 384 | Fast general-purpose |
| BGE Small | `BAAI/bge-small-en-v1.5` | 384 | Adds query prefix for asymmetric retrieval |

BGE prefixes query texts with `"Represent this sentence for searching relevant passages: "` when `is_query=True`, following the model's training convention.

#### OpenAI (Small, Large)

Calls the OpenAI Embeddings API in batches of 100 (API limit). Uses `openai.OpenAI(api_key=...)` client.

| Model | API name | Dimensions |
|-------|----------|------------|
| OpenAI Small | `text-embedding-3-small` | 1536 |
| OpenAI Large | `text-embedding-3-large` | 3072 |

#### Cohere

Uses `cohere.Client`. Batches in groups of 96. Sets `input_type="search_document"` for corpus embeddings and `input_type="search_query"` for query embeddings — required by Cohere's API for retrieval-optimized embeddings.

Model: `embed-english-v3.0`, dimensions: 1024.

---

### 3.3 Retrievers (`retrievers.py`)

All retrievers share the same interface:

```python
def retrieve(
    query: str,
    query_embedding: np.ndarray,    # shape (D,)
    corpus_embeddings: np.ndarray,  # shape (N, D)
    chunks: list[dict],
    top_k: int
) -> list[dict]:
    # returns top_k chunks, ordered by relevance score (descending)
```

Registered in the `RETRIEVERS` list.

#### Dense (`dense_retrieve`)

Builds a FAISS `IndexFlatIP` (inner product = cosine similarity on L2-normalized vectors). Searches the full index at query time.

```python
index = faiss.IndexFlatIP(D)
index.add(corpus_embeddings)
scores, indices = index.search(query_embedding[np.newaxis], top_k)
```

Time complexity: O(N·D) per query (flat exhaustive search). For production use, swap to `IndexIVFFlat` or `IndexHNSW`.

#### Sparse (`sparse_retrieve`)

BM25 via `rank_bm25.BM25Okapi`. Tokenizes by lowercasing and splitting on whitespace. Filters results with `score <= 0` (no term overlap).

```python
tokenized_corpus = [text.lower().split() for text in chunk_texts]
bm25 = BM25Okapi(tokenized_corpus)
scores = bm25.get_scores(query.lower().split())
```

BM25 is rebuilt per retrieval call (not cached across queries). For large corpora, consider caching the `BM25Okapi` object per (chunker, embedder) combination.

#### Hybrid (`hybrid_retrieve`)

Combines dense and sparse scores via **Reciprocal Rank Fusion (RRF)**:

```python
rrf_k = 60  # smoothing constant (standard value from Cormack et al. 2009)
rrf_score = Σ (weight / (rrf_k + rank_in_system))
```

Weights: `0.7` (dense) + `0.3` (sparse). Each system independently retrieves `min(top_k * 3, N)` candidates to give RRF enough candidates to fuse.

RRF is rank-based, not score-based — no normalization of scores across systems is needed, making it robust to embedding dimensionality differences.

---

### 3.4 Metrics (`metrics.py`)

All metric functions accept:

```python
retrieved_doc_ids: list[str]   # ordered, deduplicated, length = k
relevant_doc_ids: set[str]     # ground truth
k: int
```

| Metric | Formula | What it measures |
|--------|---------|-----------------|
| **Precision@K** | `\|rel ∩ top_k\| / k` | Density of relevant results in top-k |
| **Recall@K** | `\|rel ∩ top_k\| / \|rel\|` | Coverage — fraction of relevant docs found |
| **MRR** | `1 / rank(first relevant)` | How high the first relevant result appears |
| **NDCG@K** | `DCG / IDCG` | Ranking quality weighted by position |
| **MAP@K** | `avg precision at each relevant position` | Area under the precision-recall curve |
| **Hit Rate@K** | `1 if any relevant in top_k else 0` | Binary presence — at least one hit |

`evaluate_query()` returns all six metrics as a dict. The runner averages them across all queries for the aggregate results DataFrame.

---

### 3.5 Runner (`runner.py`)

`run_benchmark()` is the sole public entry point. Its iteration order is:

```
for chunker in chunker_names:
    chunks = chunker(documents)
    for embedder in embedder_names:
        corpus_embeddings = embed(chunk_texts)        # ← cached per (chunker, embedder)
        for retriever in retriever_names:
            for query in queries:
                query_embedding = embed([query.text])
                results = retrieve(...)
                metrics = evaluate_query(...)
            avg_metrics → append to results_df
```

Key design choices:
- **Corpus embeddings are computed once per (chunker, embedder) pair**, not per retriever. This avoids O(chunkers × embedders × retrievers) embedding calls — only O(chunkers × embedders) are made.
- **Doc-ID deduplication** happens after retrieval: a query may retrieve multiple chunks from the same document. We keep the highest-ranked chunk per doc, preserving rank order, before computing metrics.
- **Error isolation**: if an embedder raises (e.g., invalid API key), the runner catches the exception, records `error` in the result row, and continues to the next combination. The benchmark does not abort.
- **Progress callback**: `on_progress(pct: float, message: str)` is called after each combination, enabling real-time UI updates without coupling the runner to Streamlit.

---

## 4. Evaluation Design

### Why only retrieval metrics?

RAG quality has two components: retrieval (did we find the right chunks?) and generation (did the LLM use them well?). Generation quality requires an LLM judge and is expensive to run at scale. Retrieval quality is deterministic, fast, and the dominant driver of end-to-end performance — poor retrieval cannot be compensated by a good generator.

### Ground truth format

Ground truth is at the **document level**, not chunk level. This is intentional: you rarely know which specific chunk is relevant, but you do know which source documents are. The runner deduplicates chunk results to doc IDs before metric computation.

### Metric selection rationale

| Use case | Primary metric |
|----------|---------------|
| "Find all relevant docs" | Recall@K |
| "Minimize noise in retrieved context" | Precision@K |
| "Top result quality" | MRR |
| "Overall ranking quality" | NDCG@K |
| "Any hit is enough" | Hit Rate@K |

For most RAG systems, **Recall@K** is the primary metric — missing a relevant document is usually worse than including an irrelevant one (the LLM can ignore irrelevant context; it cannot fabricate what was never retrieved).

---

## 5. Performance Characteristics

### Embedding cost

Local models (MiniLM, BGE) run on CPU and are the fastest to start, though throughput is limited for large corpora. Approximate times on M-series Mac:

| Embedder | 1000 chunks (384-dim) |
|----------|----------------------|
| MiniLM | ~3–5 seconds |
| BGE Small | ~4–6 seconds |
| OpenAI Small | ~2–4 seconds (network-bound) |

### Memory

Corpus embeddings are held in memory as float32 numpy arrays. Memory estimate:

```
memory ≈ N_chunks × D × 4 bytes
Example: 500 chunks × 384 dims × 4B = ~0.75 MB
```

For very large corpora (>100K chunks), consider chunking in batches and using quantized FAISS indices.

### Caching

- Sentence-transformer models: cached after first load in `_local_models` dict
- Semantic chunking model: cached in `_semantic_model` module global
- Corpus embeddings: **not persisted to disk** — recomputed on each benchmark run. Add disk caching (e.g., `numpy.save`) if you run the same dataset repeatedly.

---

## 6. Extension Guide

### Adding a new chunking strategy

1. Write a function matching the interface in `src/rag_ops/chunkers.py`:

```python
def my_chunker(documents: list[dict]) -> list[dict]:
    chunks = []
    for doc in documents:
        # ... your logic ...
        chunks.append({
            "chunk_id": f"{doc['doc_id']}::mychunker_{i}",
            "doc_id": doc["doc_id"],
            "text": chunk_text,
            "metadata": {"source": doc.get("source", "")},
        })
    return chunks
```

2. Register it in the `CHUNKERS` dict:

```python
CHUNKERS = {
    ...
    "My Chunker": my_chunker,
}
```

3. Add a checkbox in `app.py` (sidebar section) and append the name to `chunker_names`.

### Adding a new embedding model

1. Write a function in `src/rag_ops/embedders.py`:

```python
def embed_mymodel(texts: list[str], api_keys: dict, is_query: bool) -> np.ndarray:
    # return float32 ndarray shape (len(texts), D), L2-normalized
    embeddings = ...
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return (embeddings / np.maximum(norms, 1e-9)).astype(np.float32)
```

2. Register in `EMBEDDERS`:

```python
EMBEDDERS = {
    ...
    "My Model": embed_mymodel,
}
```

3. Add checkbox in `app.py` sidebar and append to `embedder_names`.

### Adding a new retrieval method

1. Write a function in `src/rag_ops/retrievers.py`:

```python
def my_retrieve(query, query_embedding, corpus_embeddings, chunks, top_k):
    # return list of chunk dicts, ordered by score descending
    ...
```

2. Append to `RETRIEVERS` list and add checkbox in `app.py`.

### Adding a new metric

1. Add function in `src/rag_ops/metrics.py` and call it inside `evaluate_query()`.
2. The new key will automatically appear in `results_df` columns and the leaderboard.

---

## 7. Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=rag_ops --cov-report=term-missing

# Specific module
pytest tests/test_chunkers.py -v
```

Tests are in `tests/`. The test suite covers chunkers, embedders (mocked API calls), retrievers, metrics, and the runner integration.

---

## 8. Dependency Map

```
app.py
└── rag_ops.runner
    ├── rag_ops.chunkers
    │   └── sentence_transformers     (semantic only)
    ├── rag_ops.embedders
    │   ├── sentence_transformers     (MiniLM, BGE)
    │   ├── openai                    (OpenAI models)
    │   └── cohere                    (Cohere)
    ├── rag_ops.retrievers
    │   ├── faiss                     (dense)
    │   └── rank_bm25                 (sparse, hybrid)
    └── rag_ops.metrics          (pure Python, no deps)
```

All dependencies are declared in `pyproject.toml`. Optional API dependencies (openai, cohere) are always installed but only invoked when API keys are provided.
