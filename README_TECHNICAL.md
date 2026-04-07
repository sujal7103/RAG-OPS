# RAG-OPS Technical Architecture

This document explains the current repo architecture, data flow, and extension points. For the product-facing overview, see [README.md](README.md).

---

## System Overview

RAG-OPS evaluates the retrieval stage of a RAG pipeline. It does not generate final LLM answers. Its job is to answer:

> given a dataset of documents, labeled queries, and a retrieval configuration, which chunking + embedding + retrieval combination surfaces the right source documents best?

The current repo has two major layers:

```text
Streamlit Admin UI
        |
        v
FastAPI Service  <->  Postgres / Redis / Object Storage
        |
        v
Async Worker / Local Runner
        |
        v
Chunkers -> Embedders -> Retrievers -> Metrics
```

### Current runtime roles

- `app.py` is only a thin Streamlit entrypoint
- `src/rag_ops/ui/` contains the real Streamlit UI modules
- `src/rag_ops/api/` contains the FastAPI application
- `src/rag_ops/services/` contains runtime and run-execution services
- `src/rag_ops/workers/` contains async worker entrypoints
- `src/rag_ops/repositories/` and `src/rag_ops/db/` back persistence
- `src/rag_ops/security/` handles auth and credential protection

The UI can run in two modes:

- local Streamlit mode, which executes the benchmark directly
- API-backed mode, where Streamlit submits runs to the service layer and polls results

---

## Pipeline Data Flow

### Core inputs

```python
documents: list[Document]
queries: list[Query]
ground_truth: dict[str, set[str]]
```

### Benchmark flow

```text
documents
  -> chunker
  -> chunks
  -> embedder
  -> corpus embeddings

query
  -> query embedding
  -> retriever
  -> ranked chunks
  -> deduplicated document ids
  -> metric evaluation
  -> aggregate + per-query outputs
```

### Persisted platform flow

```text
Streamlit UI
  -> create dataset
  -> create benchmark config
  -> create run
  -> poll run status
  -> load persisted results/artifacts
```

The API-backed path persists:

- datasets and dataset versions
- benchmark configs
- runs and attempts
- aggregate results
- per-query results
- artifact metadata
- provider credentials

---

## Module Reference

### Streamlit UI

`src/rag_ops/ui/` now owns the Streamlit experience:

- `app.py`: top-level UI orchestration
- `sidebar.py`: benchmark controls, provider credential selection, and runtime config
- `data_views.py`: sample/uploaded dataset loading and previews
- `results.py`: leaderboard, charts, per-query details, and historical reports
- `api_client.py`: service client used in API-backed mode
- `state.py`: Streamlit session-state helpers
- `styles.py`: shared page styling

### Core evaluation pipeline

- `chunkers.py`: retrieval chunking strategies and registry
- `embedders.py`: local and API-backed embedding integrations
- `retrievers.py`: dense, sparse, and hybrid retrieval
- `metrics.py`: retrieval evaluation metrics
- `runner.py`: local benchmark orchestration

### Service platform

- `api/`: FastAPI app, routes, dependencies, middleware
- `services/`: benchmark-run execution, runtime, health, run-state helpers
- `repositories/platform.py`: persistence access patterns
- `db/`: SQLAlchemy models, sessions, bootstrap helpers
- `security/`: auth resolution and credential encryption
- `workers/`: async worker processes
- `object_store.py`: S3-compatible artifact handling
- `observability.py`, `metrics_registry.py`, `metrics_server.py`: logging and metrics

---

## Evaluation Design

The platform evaluates only retrieval quality, not answer generation.

Current metric set:

- `precision@k`
- `recall@k`
- `mrr`
- `ndcg@k`
- `map@k`
- `hit_rate@k`

Outputs are produced in two forms:

- aggregate result rows per configuration
- per-query detail rows for drill-down

Those outputs can be rendered directly in Streamlit and, in API-backed mode, persisted and reloaded through the service layer.

---

## Extension Guide

### Add a new chunker

1. Implement it in `src/rag_ops/chunkers.py`
2. Register it in the chunker registry
3. If it should be selectable in the UI, expose it in `src/rag_ops/ui/sidebar.py`
4. Add tests covering output shape and edge cases

### Add a new embedder

1. Implement it in `src/rag_ops/embedders.py`
2. Register it in the embedder registry
3. If it requires credentials, wire the UI/service credential path through `src/rag_ops/ui/sidebar.py` and the runtime/service execution layer
4. Add tests for shape, normalization, and provider mocking where needed

### Add a new retriever

1. Implement it in `src/rag_ops/retrievers.py`
2. Update the retrieval dispatch there
3. Expose it in `src/rag_ops/ui/sidebar.py` if user-selectable
4. Verify aggregate and per-query outputs still behave correctly

### Add a new metric

1. Implement it in `src/rag_ops/metrics.py`
2. Include it in the evaluation path
3. Verify local UI rendering and API-backed persisted result handling

Do not treat `app.py` as the main UI wiring surface anymore. User-facing benchmark controls live in `src/rag_ops/ui/sidebar.py`, while persisted/API-backed behavior lives in the service layer.

---

## Testing

Current tests cover more than the original benchmark core. The suite now includes:

- chunkers
- embedders
- retrievers
- metrics
- runner behavior
- data loading
- API platform routes
- system routes
- async runs
- auth and security
- Streamlit API client helpers

Recommended checks:

```bash
pytest -q
python3 -m compileall app.py src tests alembic monitoring
```

For service changes, also run the actual entrypoints locally:

```bash
rag-ops-api
rag-ops-worker
```

---

## Dependency Map

At a high level:

- Streamlit UI depends on UI modules, session state, and the API client
- local execution depends on `runner.py`
- API-backed execution depends on FastAPI routes, services, repositories, and workers
- both local and API-backed paths share chunkers, embedders, retrievers, metrics, validation, and data models

That shared-core design is the main architectural idea in the current repo.
