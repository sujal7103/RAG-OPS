# RAG-OPS Repo Overview

This file is a simple-English map of the repository based on the current code.

## 1. What this project is

RAG-OPS is a retrieval benchmarking platform for RAG systems.

It does **not** generate final LLM answers.
It tests which retrieval setup works best.

The project compares:

- chunking strategies
- embedding models
- retrieval methods
- retrieval metrics

Then it shows the results in a Streamlit admin UI and can also persist them through an API and worker stack.

## 2. The big idea in one sentence

You give the app documents, test queries, and the correct source-document labels.
RAG-OPS tries many retrieval pipeline combinations and tells you which one retrieves the right documents best.

## 3. What lives in this repo

At a high level, the repo has 5 main parts:

1. `app.py`
   This is the thin Streamlit entrypoint.

2. `src/rag_ops/ui/`
   This is the real Streamlit UI layer.

3. `src/rag_ops/`
   This contains the benchmark engine: chunkers, embedders, retrievers, metrics, runner, validation, and data loading.

4. `src/rag_ops/api/`, `services/`, `db/`, `repositories/`, `security/`, and `workers/`
   This is the service platform for persisted datasets, runs, credentials, async execution, and reporting.

5. `tests/`
   This contains pytest coverage for the benchmark core and the service platform.

There are also docs, screenshots, sample data, migrations, and monitoring config.

## 4. Repo shape

```text
RAG-OPS/
├── app.py
├── README.md
├── README_TECHNICAL.md
├── CONTRIBUTING.md
├── DEPLOYMENT.md
├── docker-compose.yml
├── pyproject.toml
├── alembic/
├── monitoring/
├── src/rag_ops/
│   ├── api/
│   ├── db/
│   ├── repositories/
│   ├── security/
│   ├── services/
│   ├── ui/
│   ├── workers/
│   ├── chunkers.py
│   ├── embedders.py
│   ├── retrievers.py
│   ├── metrics.py
│   ├── runner.py
│   ├── data_loading.py
│   ├── validation.py
│   └── sample_data/
└── tests/
```

## 5. How the system works now

There are two main ways to run it:

### Local Streamlit path

1. User runs `streamlit run app.py`
2. `app.py` starts the Streamlit UI in `src/rag_ops/ui/`
3. User loads data, picks chunkers/embedders/retrievers, and runs the benchmark
4. `runner.py` executes the retrieval benchmark directly
5. Streamlit renders results and per-query details

### API-backed path

1. User runs Streamlit with `RAG_OPS_API_BASE_URL`
2. Streamlit creates datasets, configs, and runs through the FastAPI service
3. The worker executes benchmark runs asynchronously
4. Results, artifacts, and history are persisted
5. Streamlit polls the API and renders historical reports too

## 6. The real architecture

The current architecture is more than a single UI file:

```text
Streamlit Admin UI
        |
        v
FastAPI API
        |
        v
Worker / Local Runner
        |
        +--> Chunkers
        +--> Embedders
        +--> Retrievers
        +--> Metrics
        |
        +--> Postgres / Redis / Object Storage
```

The benchmark core is still simple.
The platform around it is now more production-shaped.

## 7. Important data shapes

The repo works with these main concepts:

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
  "metadata": dict,
}
```

### Results

- aggregate result rows for each configuration
- per-query detail rows for drill-down
- persisted artifact metadata for completed runs

## 8. File-by-file explanation

### `app.py`

This is now only the thin entrypoint that starts the Streamlit UI.

### `src/rag_ops/ui/`

This is the real Streamlit app:

- `app.py` coordinates the workflow
- `sidebar.py` builds the benchmark controls
- `data_views.py` handles loading and previewing data
- `results.py` renders charts, tables, and history
- `api_client.py` talks to the FastAPI service in API mode
- `state.py` manages Streamlit session state
- `styles.py` defines the shared UI styling

### `src/rag_ops/chunkers.py`

Contains the chunking strategies and the chunker registry.

### `src/rag_ops/embedders.py`

Contains local and API-backed embedding integrations.

### `src/rag_ops/retrievers.py`

Contains dense, sparse, and hybrid retrieval logic.

### `src/rag_ops/metrics.py`

Contains the retrieval evaluation metrics.

### `src/rag_ops/runner.py`

This is the local benchmark orchestrator.

### `src/rag_ops/api/`

Contains the FastAPI service and route wiring.

### `src/rag_ops/services/`

Contains benchmark-run services, runtime helpers, and health logic.

### `src/rag_ops/repositories/` and `src/rag_ops/db/`

Contain persistence logic and database models.

### `src/rag_ops/security/`

Contains auth and credential-encryption logic.

### `src/rag_ops/workers/`

Contains the async worker entrypoints.

## 9. What is good about the repo

- The core benchmark idea is easy to understand
- The extension points for chunkers, embedders, retrievers, and metrics are still clear
- The UI remains easy to run locally
- The project now also has a serious backend shape for persisted runs and reporting

## 10. What contributors should know

- Do not assume `app.py` is the whole UI anymore
- Streamlit controls are mainly wired in `src/rag_ops/ui/sidebar.py`
- The repo now has both local execution and API-backed execution
- Docs that describe the project as a single-file Streamlit app are outdated

## 11. Bottom line

RAG-OPS started as a retrieval benchmark UI and is now a retrieval benchmark platform.

The core job is still simple:
compare retrieval setups and find the winner.

The difference now is that the repo also includes the backend pieces needed for persisted runs, async execution, credentials, reporting, and deployment.
