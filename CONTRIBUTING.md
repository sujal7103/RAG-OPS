# Contributing to RAG-OPS

Thanks for your interest in contributing. RAG-OPS now has two layers:

- a Streamlit-first admin UI for running and inspecting benchmarks
- a service platform underneath for persisted datasets, runs, credentials, reporting, and async execution

This guide is meant to help contributors work safely in the current repo shape.

---

## Ways To Contribute

High-impact areas:

- new chunking strategies
- new embedding models
- new retrieval methods
- new evaluation metrics
- benchmark performance and caching improvements
- Streamlit workflow polish
- API, worker, auth, and reporting improvements
- tests and docs

---

## Getting Started

### Clone and set up the environment

```bash
git clone https://github.com/sujal7103/RAG-OPS.git
cd RAG-OPS
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Basic verification

For any contribution:

```bash
pytest -q
streamlit run app.py
```

For backend, service, auth, worker, or deployment-related changes, also verify:

```bash
rag-ops-api
rag-ops-worker
```

If you are working on docs or broad repo consistency, also run:

```bash
python3 -m compileall app.py src tests alembic monitoring
```

---

## Project Structure

```text
RAG-OPS/
├── app.py                          # Thin Streamlit entrypoint
├── src/rag_ops/
│   ├── ui/                         # Streamlit UI modules
│   ├── api/                        # FastAPI routes, dependencies, middleware
│   ├── services/                   # Run execution and health/runtime services
│   ├── security/                   # Auth and credential encryption
│   ├── repositories/               # Persistence repositories
│   ├── db/                         # SQLAlchemy models and sessions
│   ├── workers/                    # Async worker entrypoints
│   ├── runner.py                   # Benchmark orchestration
│   ├── chunkers.py                 # Chunking strategies
│   ├── embedders.py                # Embedding integrations
│   ├── retrievers.py               # Retrieval methods
│   ├── metrics.py                  # Evaluation metrics
│   ├── data_loading.py             # Dataset loading helpers
│   ├── cache.py                    # Local cache helpers
│   ├── object_store.py             # Artifact upload/storage helpers
│   └── settings.py                 # Runtime settings
└── tests/                          # Unit and integration tests
```

For a deeper architecture walk-through, see [README_TECHNICAL.md](README_TECHNICAL.md).

---

## Adding New Components

The core evaluation pipeline is still built around simple registries and clear interfaces.

### New chunking strategy

Add the implementation in `src/rag_ops/chunkers.py` and register it in `CHUNKERS`.

If the new strategy should be user-selectable in the Streamlit UI, expose it in `src/rag_ops/ui/sidebar.py` so it is included in `BenchmarkConfig`.

If the change affects how configs are described or validated, update the service-facing path as needed so API-backed runs can use it too.

### New embedding model

Add the implementation in `src/rag_ops/embedders.py` and register it in `EMBEDDERS`.

If it requires credentials:

- local-only key entry belongs in the Streamlit sidebar flow
- API-backed credential binding belongs in `src/rag_ops/ui/sidebar.py` and the service/runtime path

Do not wire new models only into the UI. They must work for both local execution and API-backed execution where applicable.

### New retrieval method

Add the implementation in `src/rag_ops/retrievers.py` and update the retrieval dispatch there.

If it should be selectable from the UI, expose it in `src/rag_ops/ui/sidebar.py`.

If it changes result semantics or stored outputs, update any affected reporting/tests.

### New metric

Add the metric in `src/rag_ops/metrics.py` and ensure the aggregate/per-query evaluation path includes it.

If it should appear in historical reports or visualizations, verify the result rendering paths still work in both local and API-backed modes.

---

## Code Style

We use `ruff` for linting and formatting:

```bash
ruff check src tests
ruff check --fix src tests
ruff format src tests
```

Conventions:

- use type hints on public functions
- add concise docstrings on public functions
- keep modules focused
- prefer explicit code over clever shortcuts
- avoid hidden coupling between UI-only code and service-only code

---

## Testing

Common commands:

```bash
pytest -q
pytest --cov=rag_ops --cov-report=term-missing
pytest tests/test_chunkers.py -v
```

Areas already covered in the current suite include:

- chunkers
- embedders
- retrievers
- metrics
- runner behavior
- data loading
- API platform routes
- system routes
- async run execution
- auth and security behavior
- Streamlit API client helpers

When adding features, prefer tests that cover:

- happy path behavior
- invalid input or configuration
- API-backed mode if the feature touches service execution
- credential or auth handling if the feature touches secured flows

For external provider integrations, mock the client calls rather than depending on live APIs.

---

## Pull Requests

1. Branch from `main`
2. Keep the change focused
3. Add or update tests where behavior changes
4. Run the relevant checks
5. Update docs when architecture, commands, or contributor workflow changes

### PR checklist

- [ ] Tests added or updated where needed
- [ ] `pytest -q` passes
- [ ] `ruff check src tests` passes
- [ ] Streamlit UI wiring updated in `src/rag_ops/ui/sidebar.py` when adding user-selectable pipeline options
- [ ] Core registry/runner/service wiring updated where required
- [ ] Docs updated if commands, architecture, or extension points changed

---

## Reporting Bugs

Open an issue with:

- expected behavior
- actual behavior
- steps to reproduce
- traceback or error message
- environment details

If the bug is API-backed, include whether you were using:

- local Streamlit-only execution
- Streamlit with `RAG_OPS_API_BASE_URL`
- full API + worker stack

---

## Suggesting Features

Open an issue and describe:

- the problem you want to solve
- how it fits the existing benchmark workflow
- any prior art or references

For large changes to architecture, auth, deployment, or UI flow, discuss the approach first before opening a big PR.
