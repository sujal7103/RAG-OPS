# RAG-OPS Repo Overview

This file is a plain-English map of the repository based on the actual code in the repo.

## 1. What this project is

RAG-OPS is a small benchmarking app for the retrieval part of a RAG system.

It does **not** generate final LLM answers.
It measures how good different retrieval setups are.

The project compares:

- chunking strategies
- embedding models
- retrieval methods
- retrieval metrics

Then it shows the results in a Streamlit dashboard.

## 2. The big idea in one sentence

You give the app some documents, some test queries, and the correct document labels for each query.
The app tries many pipeline combinations and tells you which combination retrieves the right documents best.

## 3. What lives in this repo

At a high level, the repo has 3 main parts:

1. `app.py`
   This is the Streamlit UI. It is the front door of the project.

2. `src/rag_ops/`
   This is the real engine. It contains chunkers, embedders, retrievers, metrics, and the runner.

3. `tests/`
   This contains a small pytest suite for some core behavior.

There are also docs, screenshots, and built-in sample data.

## 4. Repo shape

```text
rag-ops-main/
├── app.py
├── pyproject.toml
├── README.md
├── README_TECHNICAL.md
├── CONTRIBUTING.md
├── .streamlit/config.toml
├── src/rag_ops/
│   ├── __init__.py
│   ├── chunkers.py
│   ├── embedders.py
│   ├── retrievers.py
│   ├── metrics.py
│   ├── runner.py
│   └── sample_data/
│       ├── corpus/
│       └── queries.json
└── tests/
    ├── test_chunkers.py
    ├── test_metrics.py
    └── test_runner.py
```

## 5. Quick code facts

- The codebase is mostly function-based.
- There are no classes in the Python source files.
- The main UI is a single large file: `app.py` is 836 lines.
- The package code in `src/rag_ops/*.py` is small and focused.
- The Python code in `app.py`, `src/`, and `tests/` is about 1,831 lines total.

## 6. How the app works from start to finish

When a user runs `streamlit run app.py`, this is the real flow:

1. Streamlit loads `app.py`.
2. The page config and a large custom CSS block are applied.
3. The sidebar lets the user choose chunkers, embedders, retrievers, API keys, and `top_k`.
4. The user loads either:
   - built-in sample data, or
   - uploaded `.txt` / `.md` documents plus a `queries.json` file
5. When the user clicks **Run Benchmark**, `app.py` imports `run_benchmark()` from `src/rag_ops/runner.py`.
6. The runner loops through every selected combination.
7. For each query, it retrieves documents and scores them with retrieval metrics.
8. The UI stores the results in `st.session_state`.
9. The results screen shows tables, heatmaps, charts, and per-query details.

## 7. The real architecture

The architecture is simple and clean:

```text
Streamlit UI (app.py)
        |
        v
Runner (runner.py)
        |
        +--> Chunkers (chunkers.py)
        +--> Embedders (embedders.py)
        +--> Retrievers (retrievers.py)
        +--> Metrics (metrics.py)
```

The runner is the coordinator.
Each module does one job.

## 8. Important data shapes

The code repeatedly uses these shapes:

### Documents

```python
{"doc_id": str, "content": str, "source": str}
```

### Queries

```python
{"query_id": str, "query": str}
```

### Ground truth

```python
{query_id: set_of_relevant_doc_ids}
```

### Chunks

```python
{
  "chunk_id": str,
  "doc_id": str,
  "text": str,
  "metadata": dict
}
```

### Final results

- one aggregate `DataFrame`
- one `per_query_results` dictionary for detailed drill-down

## 9. File-by-file explanation

### `app.py`

This is the UI script and also the app controller.

What it does:

- sets up the Streamlit page
- injects a large custom light-theme CSS block
- loads sample or uploaded data
- keeps state in `st.session_state`
- builds sidebar controls
- validates selections
- runs the benchmark
- renders result tables and charts
- lets users download CSV and JSON output

Important design detail:

Most of `app.py` is top-to-bottom Streamlit code, not helper functions.
Only two real helper functions exist here:

- `load_sample_data()`
- `load_uploaded_data()`

Everything else is UI logic that executes during page render.

### `src/rag_ops/__init__.py`

Very small file.
It only provides a package docstring and `__version__ = "0.1.0"`.

### `src/rag_ops/chunkers.py`

This file turns full documents into smaller pieces.

It contains 4 chunking strategies:

#### 1. `fixed_size_chunk`

- splits text by character count
- uses overlap
- tries not to cut words in half
- stores chunk start/end in metadata

This is the simplest baseline chunker.

#### 2. `recursive_chunk`

- tries bigger natural separators first
- order is: paragraph break, newline, sentence-ish split, then space
- if a piece is still too large, it recurses into a smaller separator
- adds overlap by copying the tail of the previous chunk

This is better for normal text than raw fixed-size chunking.

#### 3. `semantic_chunk`

- splits text into sentences
- embeds each sentence with `sentence-transformers`
- compares neighboring sentence vectors
- starts a new chunk when similarity drops below a threshold

This is the smartest chunker in the repo, but also the heaviest one.
It loads a sentence-transformer model lazily through `_get_semantic_model()`.

#### 4. `document_aware_chunk`

- respects markdown headings
- keeps fenced code blocks together
- falls back to paragraph splitting when no headings exist
- further splits large sections by paragraph

This chunker is aimed at README-style or docs-like content.

Other important pieces in this file:

- `CHUNKERS`
  A registry mapping display names to functions.
- `chunk_documents()`
  Loops over all documents and applies one selected chunker.

### `src/rag_ops/embedders.py`

This file converts text into vectors.

It has 5 user-facing embedders:

- `MiniLM`
- `BGE Small`
- `OpenAI Small`
- `OpenAI Large`
- `Cohere`

Key behavior:

- local `sentence-transformers` models are cached in `_models`
- returned vectors are normalized
- OpenAI calls are batched by 100 texts
- Cohere calls are batched by 96 texts
- BGE adds a special prefix for query embeddings

Important dispatch pieces:

- `EMBEDDERS`
  Registry of embedder name, function, and API-key requirement.
- `embed_texts()`
  Main public helper used by the runner.

### `src/rag_ops/retrievers.py`

This file ranks chunks for a query.

It contains 3 retrieval modes:

#### Dense

- uses FAISS
- uses inner product on normalized vectors
- effectively behaves like cosine similarity

#### Sparse

- uses BM25 from `rank_bm25`
- tokenizes by lowercasing and splitting on spaces

#### Hybrid

- runs both dense and sparse retrieval
- combines them with Reciprocal Rank Fusion (RRF)
- uses a dense weight of `0.7` and sparse weight of `0.3`

Important dispatch pieces:

- `RETRIEVERS`
  Simple list of valid retriever names.
- `retrieve()`
  Chooses the correct retrieval function based on the selected name.

### `src/rag_ops/metrics.py`

This file scores retrieval quality.

It contains 6 metrics:

- `precision_at_k`
- `recall_at_k`
- `mrr`
- `ndcg_at_k`
- `map_at_k`
- `hit_rate_at_k`

`evaluate_query()` returns all 6 metrics at once for one query.

Important detail:

The metrics are computed on **document IDs**, not chunk IDs.
That means the system cares about finding the right source documents, not the exact chunk positions.

### `src/rag_ops/runner.py`

This is the core engine.
It is the most important backend file in the repo.

`run_benchmark()` does the orchestration.

Its job is:

1. chunk the documents
2. embed the chunks
3. loop through each retriever
4. embed each query
5. retrieve results
6. deduplicate repeated document IDs
7. score the retrieval output
8. average the scores across queries
9. return aggregate and per-query results

Good design choices in this file:

- corpus embeddings are computed once per chunker + embedder pair
- embedder failures do not crash the whole benchmark
- progress can be reported back to the UI
- final results are sorted by `recall@k`

### `src/rag_ops/sample_data/`

This is a built-in demo dataset.

What is inside:

- 10 small `.txt` documents
- 15 queries in `queries.json`

The sample documents are short Python tutorial notes about:

- basics
- data structures
- functions
- OOP
- file handling
- error handling
- modules
- web development
- data science
- testing

This makes the app usable immediately without setup.

### `tests/`

The test suite is small but useful.

What is covered:

- fixed-size chunking
- recursive chunking
- document-aware chunking
- metrics math
- one end-to-end runner test with a mocked embedder

What is not covered right now:

- semantic chunking
- retriever functions directly
- embedder functions directly
- Streamlit UI behavior

## 10. What happens when the benchmark runs

Here is the actual loop shape in simple words:

1. pick one chunker
2. chunk all documents
3. pick one embedder
4. embed all chunks once
5. pick one retriever
6. for each query:
   - embed the query
   - retrieve top results
   - keep only unique `doc_id` values in rank order
   - score the result against ground truth
7. average the metrics for that configuration
8. move to the next configuration

This is why the tool is easy to extend.
Each step is separated.

## 11. Why the repo feels easy to understand

The repo has a few strong design habits:

- each backend module has one clear responsibility
- function names are direct and readable
- most data is passed around as simple dictionaries and arrays
- registries (`CHUNKERS`, `EMBEDDERS`, `RETRIEVERS`) make extension easy
- the runner keeps the overall flow in one place

## 12. Things that are important to know

These are practical truths I found from reading the real code:

### 1. This is a retrieval benchmark, not a full RAG app

There is no generation stage, no prompt building, and no LLM answer scoring.

### 2. The UI is big and monolithic

`app.py` contains styling, data loading, validation, benchmark execution, and result rendering in one file.
It works, but future refactoring could split it into smaller UI helpers.

### 3. Some work is repeated

In `runner.py`, query embeddings are recalculated inside the retriever loop.
That means the same query may be re-embedded multiple times for the same embedder.

### 4. Retrieval indexes are rebuilt often

- FAISS index is built each dense query call
- BM25 object is built each sparse query call

This is fine for small demos, but it will cost time on larger datasets.

### 5. There is no Streamlit caching

The app does not use `st.cache_data` or `st.cache_resource`.
So repeated runs recompute everything.

### 6. Some declared dependencies are not used in the current code

`pyproject.toml` declares:

- `tiktoken`
- `pymupdf`
- `matplotlib`

But the current Python source does not import or use them.
They may be planned for future features.

### 7. The tests need the package path or package install

Running plain `pytest` in this workspace failed because `rag_ops` was not importable by default.
Running with `PYTHONPATH=src` fixed import discovery.

### 8. One test still depends on missing runtime dependencies in this environment

With `PYTHONPATH=src pytest -q`, the suite reached:

- 18 passing tests
- 1 failing test

The remaining failure was not a logic failure in the test itself.
It happened because `pandas` was not installed in the current Python environment, and `runner.py` imports `pandas` at module import time.

### 9. The docs are slightly ahead of the code in a few places

Examples:

- `CONTRIBUTING.md` mentions `test_embedders.py` and `test_retrievers.py`, but those files are not present.
- `README_TECHNICAL.md` describes the architecture well, but some details are more idealized than the exact current implementation.

## 13. Real extension points

If someone wants to add features, the cleanest places are:

- add a chunker in `chunkers.py` and register it in `CHUNKERS`
- add an embedder in `embedders.py` and register it in `EMBEDDERS`
- add a retriever in `retrievers.py` and wire it into `retrieve()`
- add a metric in `metrics.py` and include it in `evaluate_query()`
- add the matching UI checkbox in `app.py`

This project is clearly built to be extended through registries plus a small amount of UI wiring.

## 14. If you want to understand the repo quickly, read in this order

1. `README.md`
2. `src/rag_ops/runner.py`
3. `src/rag_ops/chunkers.py`
4. `src/rag_ops/embedders.py`
5. `src/rag_ops/retrievers.py`
6. `src/rag_ops/metrics.py`
7. `app.py`
8. `tests/`

This order helps because `runner.py` shows how everything connects.

## 15. Final summary

This repo is a compact retrieval benchmarking toolkit with:

- one large Streamlit app
- a clean five-part backend engine
- built-in sample data
- a basic but useful test suite
- easy extension points

The code is generally simple, readable, and modular.
Its biggest strengths are clarity and approachability.
Its biggest current limitations are repeated computation, a large single-file UI, and partial test coverage.
