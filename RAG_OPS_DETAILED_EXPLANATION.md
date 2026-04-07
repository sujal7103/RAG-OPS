# RAG-OPS Explained In Simple English

## 1. What this project is

RAG-OPS is a benchmarking platform for retrieval systems used in RAG applications.

RAG means "Retrieval-Augmented Generation".

In simple words:

- A user asks a question.
- The system first searches for useful documents or document chunks.
- Then an LLM can use that retrieved context to answer the question.

This project focuses on the retrieval part.

It does **not** mainly try to answer the question with a chatbot.
It tries to answer a different engineering question:

"Which retrieval setup works best for my dataset?"

That is the core idea of this project.

RAG-OPS helps compare:

- different chunking strategies
- different embedding models
- different retrievers
- the final quality of those combinations on a labeled dataset

So this project is really an **evaluation and comparison system** for retrieval pipelines.

## 2. Why this project exists

When people build RAG systems, they usually have many choices:

- How should documents be split?
- Which embedder should be used?
- Should retrieval be dense, sparse, or hybrid?
- How many results should be returned?

Most teams guess these choices or test them manually.

That becomes messy very quickly.

RAG-OPS solves that by giving you a repeatable benchmark flow:

1. Load documents and test queries.
2. Provide ground-truth labels saying which documents are relevant to which queries.
3. Run many retrieval combinations.
4. Measure the results with retrieval metrics.
5. Show which setup performs best.

This makes retrieval choices more scientific and less based on guesswork.

## 3. What problem it solves

This project helps answer:

- Which chunker works best for my dataset?
- Which embedder gives better retrieval quality?
- Is dense retrieval better than sparse for my use case?
- Which combination gives the best recall, precision, MRR, or NDCG?
- Can I save and compare runs over time?
- Can I make this usable beyond one local script?

So this is not just a research toy.
It is moving toward a serious product for retrieval evaluation and RAG experimentation.

## 4. The big picture architecture

Today, this repo has two main ways to work:

### Local app mode

This is the simplest mode.

- You run the Streamlit app.
- The UI loads data.
- The benchmark engine runs in the same app process.
- Results are shown immediately.

This is great for:

- demos
- learning
- quick experiments
- personal use

### API-backed platform mode

This is the more product-like mode.

- Streamlit still acts as the main admin UI.
- But instead of doing everything directly, it can call the FastAPI backend.
- The backend stores datasets, configs, runs, results, and credentials.
- A worker executes benchmark runs asynchronously.
- Redis can track progress and cancellation.
- Postgres or SQLite stores persistent state.
- Object storage can store artifact bundles.

This mode is for:

- serious usage
- saved history
- repeatable runs
- multi-step workflows
- production-style architecture

## 5. The main parts of the system

The project is easier to understand if you think of it as 7 layers.

### Layer 1: User interface

The main user interface is Streamlit.

Important files:

- `app.py`
- `src/rag_ops/ui/app.py`
- `src/rag_ops/ui/sidebar.py`
- `src/rag_ops/ui/data_views.py`
- `src/rag_ops/ui/results.py`
- `src/rag_ops/ui/state.py`
- `src/rag_ops/ui/styles.py`
- `src/rag_ops/ui/api_client.py`

What this layer does:

- lets the user load sample or uploaded data
- lets the user choose chunkers, embedders, and retrievers
- lets the user launch a run
- shows progress
- shows results, charts, and per-query details
- optionally talks to the API instead of doing everything locally

### Layer 2: Benchmark engine

This is the heart of the project.

Important file:

- `src/rag_ops/runner.py`

What it does:

- validates input
- creates chunks from documents
- generates embeddings
- builds retriever resources
- runs retrieval for each query
- computes retrieval metrics
- stores result rows and per-query details
- optionally saves run artifacts

This is the "real work" part of the project.

### Layer 3: Core retrieval components

Important files:

- `src/rag_ops/chunkers.py`
- `src/rag_ops/embedders.py`
- `src/rag_ops/retrievers.py`
- `src/rag_ops/metrics.py`
- `src/rag_ops/cache.py`

What they do:

- chunkers split documents into smaller pieces
- embedders convert text into vectors
- retrievers search for the most relevant chunks
- metrics score how good the retrieved results are
- cache helps avoid recomputing expensive work

### Layer 4: API layer

Important files:

- `src/rag_ops/api/app.py`
- `src/rag_ops/api/routes/platform.py`
- `src/rag_ops/api/routes/system.py`
- `src/rag_ops/api/routes/security.py`
- `src/rag_ops/api/middleware.py`
- `src/rag_ops/api/dependencies.py`

What it does:

- exposes endpoints for datasets, configs, runs, results, artifacts, and credentials
- provides health and readiness endpoints
- gives the UI or other clients a clean service boundary

### Layer 5: Service and worker layer

Important files:

- `src/rag_ops/services/benchmark_runs.py`
- `src/rag_ops/services/run_state.py`
- `src/rag_ops/services/health.py`
- `src/rag_ops/workers/main.py`
- `src/rag_ops/workers/tasks.py`

What it does:

- creates queued runs
- executes runs outside the request cycle
- tracks progress
- handles retries
- supports cancellation
- writes final outputs

### Layer 6: Database and repository layer

Important files:

- `src/rag_ops/db/models.py`
- `src/rag_ops/db/session.py`
- `src/rag_ops/db/bootstrap.py`
- `src/rag_ops/repositories/platform.py`

What it does:

- stores datasets and versions
- stores benchmark configs
- stores benchmark runs
- stores results and artifacts
- stores users, workspaces, memberships, and credentials
- gives higher layers a clean interface for persistence

### Layer 7: Security and operations layer

Important files:

- `src/rag_ops/security/auth.py`
- `src/rag_ops/security/credentials.py`
- `src/rag_ops/observability.py`
- `src/rag_ops/metrics_registry.py`
- `src/rag_ops/object_store.py`
- `src/rag_ops/redis_client.py`
- `src/rag_ops/settings.py`

What it does:

- resolves who the current user is
- enforces workspace-level access
- encrypts provider secrets
- exposes metrics
- uploads artifacts to object storage
- manages environment-based settings

## 6. The simplest mental model for this project

You can think of the whole project like this:

- Input: documents + queries + ground truth
- Engine: chunk -> embed -> retrieve -> score
- Output: ranked benchmark results

Everything else exists to make that core loop usable as a real product.

That means:

- UI makes it easy to run
- API makes it reusable
- database makes it persistent
- worker makes it asynchronous
- security makes it safer
- monitoring makes it operable

## 7. What the user does in the app

The main Streamlit flow is very simple.

### Step 1: Load data

The user can:

- load the built-in sample dataset
- upload `.txt` or `.md` documents
- upload a `queries.json` file

This is handled mainly by:

- `src/rag_ops/ui/data_views.py`
- `src/rag_ops/data_loading.py`

The documents become `Document` objects.
The queries become `Query` objects.
The relevant document mapping becomes `ground_truth`.

### Step 2: Choose the benchmark setup

The user chooses:

- chunkers
- embedders
- retrievers
- top-k
- provider credentials if needed

This is handled mainly by:

- `src/rag_ops/ui/sidebar.py`

### Step 3: Run the benchmark

The app either:

- runs directly in the Streamlit process, or
- creates a config and run through the API, then polls for status

This is handled mainly by:

- `src/rag_ops/ui/app.py`

### Step 4: See the results

The app shows:

- leaderboard
- heatmaps
- charts
- per-query details
- saved artifact information

This is handled mainly by:

- `src/rag_ops/ui/results.py`

## 8. The core data objects

The file `src/rag_ops/models.py` defines the shared data models used across the system.

The most important ones are:

### `Document`

Represents one source document.

Main fields:

- `doc_id`
- `content`
- `source`

### `Query`

Represents one benchmark query.

Main fields:

- `query_id`
- `query`

### `Chunk`

Represents a smaller piece cut from a document.

Main fields:

- `chunk_id`
- `doc_id`
- `text`
- `metadata`

### `BenchmarkConfig`

Represents the selected benchmark setup.

Main fields:

- chunker names
- embedder names
- retriever names
- top-k
- api keys
- credential bindings

### `BenchmarkRow`

Represents one final result row for one combination.

It stores:

- chunker
- embedder
- retriever
- precision@k
- recall@k
- mrr
- ndcg@k
- map@k
- hit_rate@k
- latency
- chunk stats
- error

### `BenchmarkArtifacts`

Represents saved output files for a run.

It stores paths to:

- summary JSON
- results CSV
- results JSON
- per-query JSON

## 9. How data is loaded

Data loading is handled in `src/rag_ops/data_loading.py`.

There are 3 main loading paths:

### Built-in sample data

Files live in:

- `src/rag_ops/sample_data/corpus/`
- `src/rag_ops/sample_data/queries.json`

This is useful for:

- demos
- testing the app quickly
- understanding the expected format

### Local filesystem data

The CLI can load:

- documents from a local directory
- queries from a JSON file

### Uploaded data

The Streamlit app can accept uploaded files and convert them to typed objects.

The project also validates:

- that documents are valid
- that queries are valid
- that ground-truth labels point to existing document IDs

That validation happens in:

- `src/rag_ops/validation.py`

## 10. How chunking works

Chunking means splitting a large document into smaller pieces that retrieval can search more easily.

The project currently includes chunking strategies in `src/rag_ops/chunkers.py`.

### Fixed Size

This splits by character size with overlap.

Good for:

- simplicity
- consistency
- fast baselines

### Recursive

This tries to split more naturally.
It prefers:

- paragraph breaks
- line breaks
- sentence boundaries
- then spaces

This usually preserves meaning better than blind fixed-size splitting.

### Semantic

This splits based on similarity between neighboring sentences.

It tries to keep semantically related sentences together.

This is more advanced, but more expensive.

### Document-Aware

This respects structure like:

- headings
- paragraphs
- code blocks

This is especially useful for markdown or structured docs.

### Why chunking matters

Chunking strongly affects retrieval quality.

If chunks are too large:

- retrieval becomes noisy
- irrelevant text gets mixed in

If chunks are too small:

- context gets broken apart
- relevant meaning may be lost

So chunking is one of the most important variables in RAG.

## 11. How embeddings work

Embeddings turn text into vectors.

Vectors let the system compare meaning mathematically.

This logic lives in `src/rag_ops/embedders.py`.

The project supports:

### MiniLM

- local model
- fast
- small
- free to run locally

### BGE Small

- local model
- strong retrieval performance
- also free locally

### OpenAI embeddings

- API-based
- good quality
- costs money

### Cohere embeddings

- API-based
- retrieval-oriented
- costs money

The code normalizes embeddings so similarity search behaves consistently.

It also loads local models lazily, which means:

- models are only loaded when needed
- startup is lighter
- repeated calls can reuse the model

## 12. How retrieval works

Retrieval logic lives in `src/rag_ops/retrievers.py`.

The project supports 3 retrieval types.

### Dense retrieval

This uses vector similarity.

How it works:

- chunks are embedded
- queries are embedded
- the system compares vectors
- highest similarity wins

If `faiss` is available, it uses FAISS.
If not, it falls back to a NumPy-based approach.

### Sparse retrieval

This is keyword-style retrieval.

How it works:

- it looks at token overlap and term importance
- it prefers exact lexical matches

If `rank_bm25` is installed, it uses that.
If not, it uses a fallback BM25-like implementation.

### Hybrid retrieval

This combines dense and sparse retrieval.

Why this is useful:

- dense retrieval catches semantic similarity
- sparse retrieval catches exact keyword matches
- hybrid often gives a better balance

This project combines them with Reciprocal Rank Fusion.

## 13. How scoring works

After retrieval, the project compares the retrieved document IDs with the expected relevant document IDs.

It then computes metrics such as:

### Precision@K

Of the top K retrieved results, how many were actually relevant?

### Recall@K

Of all relevant documents, how many did we successfully retrieve in the top K?

### MRR

How early did we retrieve the first correct result?

### NDCG@K

How good was the ranking quality overall?

### MAP@K

How good was precision across positions in the ranked list?

### Hit Rate@K

Did we retrieve at least one correct result in the top K?

These metrics help answer different questions.

For example:

- recall matters if missing useful context is dangerous
- precision matters if noisy retrieval is harmful
- MRR matters if first results are very important

## 14. What `runner.py` really does

`src/rag_ops/runner.py` is the core execution pipeline.

This file is worth studying carefully.

At a high level, it does this:

1. Validates inputs.
2. Loops over chunkers.
3. Chunks all documents.
4. Loops over embedders.
5. Embeds all chunks.
6. Prepares retriever resources.
7. Loops over retrievers.
8. Runs every query.
9. Scores the retrieved results.
10. Produces aggregate result rows.
11. Produces per-query details.
12. Optionally saves artifact files.

So if you want to understand the real benchmark engine, this is the most important file.

## 15. Local mode vs API mode

This is one of the most important things to understand.

### Local mode

In local mode, Streamlit directly calls `run_benchmark(...)`.

That means:

- easier to understand
- fewer moving parts
- great for learning
- great for personal experiments

### API mode

In API mode, Streamlit acts more like a client.

It does this:

1. persists the dataset
2. persists the benchmark config
3. creates a run
4. asks the worker to execute it
5. polls run status
6. fetches persisted results and artifacts

This mode is more realistic for a production product.

## 16. How the Streamlit app works internally

The entrypoint `app.py` is intentionally tiny.

It only calls `run_app()` from:

- `src/rag_ops/ui/app.py`

That file is the real Streamlit controller.

It does things like:

- set up the page
- initialize session state
- render the sidebar
- render dataset loading
- decide whether to run locally or through the API
- render final results

This is a good design choice because it keeps `app.py` simple and keeps the UI modular.

## 17. What the sidebar does

The sidebar in:

- `src/rag_ops/ui/sidebar.py`

is very important.

It is where the user selects:

- chunkers
- embedders
- retrievers
- top-k
- API credentials
- API-backed options

So if you want to change the UI controls, this is one of the first files to read.

## 18. What the API does

The API exists so the system can behave like a real platform, not just a local app.

The main API file is:

- `src/rag_ops/api/app.py`

It creates the FastAPI app and attaches:

- middleware
- routes
- settings
- startup behavior
- Redis client

The route modules are split by responsibility.

### `system.py`

Provides:

- `/`
- `/health`
- `/ready`
- `/metrics`

These are for:

- liveness
- readiness
- monitoring

### `platform.py`

Provides the main product routes:

- datasets
- configs
- runs
- results
- artifacts
- comparisons
- leaderboard

### `security.py`

Provides security-related endpoints such as identity and credentials.

## 19. How benchmark runs are created in API mode

This flow goes through:

- `src/rag_ops/api/routes/platform.py`
- `src/rag_ops/repositories/platform.py`
- `src/rag_ops/services/benchmark_runs.py`

The flow is:

1. UI sends `POST /v1/runs`.
2. The API stores the run in the database.
3. The API enqueues the run.
4. A worker or fallback thread executes the run.
5. Progress is updated while the run is working.
6. Results and artifacts are persisted when finished.

This is a major improvement over doing everything inside one Streamlit request.

## 20. What the worker does

The worker exists so long benchmark runs do not block the API or UI.

Important files:

- `src/rag_ops/workers/main.py`
- `src/rag_ops/workers/tasks.py`
- `src/rag_ops/services/benchmark_runs.py`

The worker can use:

- Dramatiq for queue-based execution, or
- a thread fallback in simpler setups

The worker also supports:

- retries for retryable failures
- cancellation
- progress tracking
- dead-letter recording for terminal failures

This makes the project more production-like.

## 21. How progress and cancellation work

This is handled by:

- `src/rag_ops/services/run_state.py`

The system stores:

- progress percentage
- current stage
- cancel requests

If Redis is enabled:

- progress and cancel state are stored in Redis

If Redis is not enabled:

- the project falls back to in-memory storage

This is a smart design because the system can still work locally without full infrastructure.

## 22. How persistence works

Persistence means "saving important things so they still exist later".

This logic is mainly in:

- `src/rag_ops/db/models.py`
- `src/rag_ops/repositories/platform.py`

The project stores:

- datasets
- dataset versions
- documents
- queries
- benchmark configs
- benchmark runs
- result rows
- per-query results
- artifacts
- users
- workspaces
- memberships
- provider credentials
- audit events

This is what moves the project from "demo tool" to "platform".

## 23. Why datasets are versioned

The system stores dataset versions instead of treating a dataset as one loose object.

This matters because:

- data can change over time
- you need reproducibility
- old runs should still make sense later

If you rerun a benchmark six months later, you want to know exactly which version of the dataset was used.

That is why versioning exists.

## 24. Why configs are persisted

Benchmark configs are also stored.

That means the system remembers:

- selected chunkers
- selected embedders
- selected retrievers
- top-k
- related fingerprints

This helps with:

- reproducibility
- history
- comparison
- reporting

## 25. How the repository layer helps

`src/rag_ops/repositories/platform.py` is a very important file.

It acts like a bridge between the service logic and the database.

Instead of scattering SQL queries everywhere, the project centralizes persistence here.

This file handles operations like:

- create dataset
- list datasets
- get dataset
- create config
- create run
- fetch run
- save results
- save artifacts
- compare runs
- build leaderboards
- manage credentials

This is a good pattern because it keeps the API and services cleaner.

## 26. How authentication works

Authentication logic lives in:

- `src/rag_ops/security/auth.py`

This file resolves who the current user is.

The project supports different auth modes:

### Disabled or none

Everything behaves like a system-owned environment.

### Dev mode

Useful for local development.
It can create or reuse a default user and workspace.

### JWT mode

Uses bearer tokens with a shared signing secret.

### OIDC or JWKS mode

This is closer to real external identity providers.

Examples:

- Auth0
- any OIDC-compatible provider

The auth layer also checks workspace roles.

Examples of roles:

- workspace_member
- workspace_admin
- workspace_owner

## 27. How credential security works

Provider secrets are handled in:

- `src/rag_ops/security/credentials.py`

This file encrypts secrets before storing them.

In simple words:

- the plaintext API key should not be stored directly in the database
- it is encrypted first
- the system can later decrypt it when needed

The code also supports:

- active key IDs
- key rotation
- key fingerprints

This is a strong step toward production safety.

## 28. How object storage fits in

Object storage logic lives in:

- `src/rag_ops/object_store.py`

This is used for run artifacts.

Examples:

- results CSV
- summary JSON
- per-query JSON
- result bundles

If object storage is not enabled, the system can still use local files.

This again shows that the project supports both:

- simple local development
- more serious infrastructure setups

## 29. How monitoring fits in

Monitoring-related code lives in:

- `src/rag_ops/metrics_registry.py`
- `src/rag_ops/metrics_server.py`
- `src/rag_ops/observability.py`
- `src/rag_ops/api/routes/system.py`

This allows the system to expose:

- Prometheus-style metrics
- request and run metadata
- health status
- readiness status

This matters when you want to operate the system like a service, not just a local tool.

## 30. What settings control the project

The file:

- `src/rag_ops/settings.py`

is the configuration center.

It controls things like:

- API host and port
- admin UI host and port
- database URL
- Redis URL
- object storage settings
- worker settings
- retry settings
- auth mode
- credential keys
- cache directories
- run directories

One important detail:

The project gracefully falls back if `pydantic-settings` is not installed.
That makes local usage easier.

## 31. How caching helps

Caching exists because chunking and embedding can be expensive.

If the same dataset and configuration are used again, the project can reuse previous work instead of repeating everything.

This helps:

- speed
- cost
- repeated experiments

The cache layer is especially useful when using paid APIs or large local models.

## 32. What gets tested

The `tests/` folder covers many important areas.

Examples:

- chunkers
- embedders
- retrievers
- runner
- data loading
- API routes
- auth and security
- async runs
- metrics
- UI API client

This is a good sign because it shows the repo is not only built, but also checked.

## 33. What makes this project stronger than a simple demo

Many AI projects stop at:

- one UI
- one script
- one model call

This project goes further.

It includes:

- a local UI
- a real benchmark engine
- a service API
- async execution
- persistence
- auth
- encrypted credentials
- metrics
- deployment assets
- tests

That makes it feel more like a real product foundation.

## 34. What this project is not

It is useful to be clear about what the project is **not**.

It is not:

- a chatbot product by itself
- a document editing system
- a general-purpose LLM platform
- a vector database

It is mainly:

- a retrieval evaluation platform
- a benchmark runner
- an experiment comparison tool

## 35. A full end-to-end example

Here is a simple example of what happens when you run a benchmark.

1. You load 10 documents and 15 queries.
2. You say query `q01` is relevant to documents `doc_02` and `doc_05`.
3. You choose:
   - chunkers: Fixed Size, Recursive
   - embedders: MiniLM, BGE Small
   - retrievers: Dense, Hybrid
4. The system calculates all combinations.
5. For each combination, it chunks all docs.
6. It embeds all chunks.
7. It prepares the retriever.
8. It runs each query.
9. It compares the retrieved document IDs against the expected relevant IDs.
10. It computes the metrics.
11. It shows a leaderboard.
12. It highlights the best setup.

That is the project in action.

## 36. The most important files to read first

If you want to understand the repo step by step, read files in this order:

1. `app.py`
2. `src/rag_ops/ui/app.py`
3. `src/rag_ops/ui/sidebar.py`
4. `src/rag_ops/ui/data_views.py`
5. `src/rag_ops/ui/results.py`
6. `src/rag_ops/models.py`
7. `src/rag_ops/data_loading.py`
8. `src/rag_ops/runner.py`
9. `src/rag_ops/chunkers.py`
10. `src/rag_ops/embedders.py`
11. `src/rag_ops/retrievers.py`
12. `src/rag_ops/api/app.py`
13. `src/rag_ops/api/routes/platform.py`
14. `src/rag_ops/repositories/platform.py`
15. `src/rag_ops/services/benchmark_runs.py`
16. `src/rag_ops/security/auth.py`
17. `src/rag_ops/db/models.py`
18. `src/rag_ops/settings.py`

That order usually makes the project much easier to understand.

## 37. If you want to extend the project

Here is where to look.

### Add a new chunker

Edit:

- `src/rag_ops/chunkers.py`
- UI wiring in `src/rag_ops/ui/sidebar.py`
- validation if needed

### Add a new embedder

Edit:

- `src/rag_ops/embedders.py`
- UI wiring in `src/rag_ops/ui/sidebar.py`

### Add a new retriever

Edit:

- `src/rag_ops/retrievers.py`
- UI wiring in `src/rag_ops/ui/sidebar.py`

### Add new API behavior

Edit:

- `src/rag_ops/api/routes/...`
- `src/rag_ops/repositories/platform.py`
- possibly `src/rag_ops/services/...`

### Change database persistence

Edit:

- `src/rag_ops/db/models.py`
- `src/rag_ops/repositories/platform.py`
- Alembic migration files

## 38. Common confusions to avoid

### "Is this just a Streamlit project?"

No.

Streamlit is the main UI, but the repo now includes:

- API
- worker
- DB
- security
- observability
- deployment layers

### "Is this only for local experiments?"

No.

It can still be used locally, but the architecture now supports more serious usage.

### "Does this answer user questions directly like a chatbot?"

Not mainly.

Its main job is to evaluate retrieval quality.

### "Why are there both local and API paths?"

Because local mode is great for simplicity, and API mode is better for product evolution.

## 39. The strongest engineering idea in this project

The strongest idea is separation of concerns.

The project separates:

- UI
- benchmark engine
- retrieval logic
- service layer
- persistence
- auth
- worker execution
- observability

That makes the project easier to:

- understand
- test
- extend
- operate

## 40. The current maturity of the project

This project is beyond a simple prototype, but it is still evolving.

It already has:

- solid retrieval benchmarking logic
- persistent platform capabilities
- async run execution
- metrics and reporting
- security foundations

What this means:

- it is strong as a portfolio project
- it is strong as a serious learning project
- it could continue growing into a real product

## 41. Short summary in one paragraph

RAG-OPS is a retrieval benchmarking platform for RAG systems. It lets a user load labeled documents and queries, try different chunking, embedding, and retrieval strategies, score them with retrieval metrics, and compare the results. It started as a Streamlit benchmarking app, but the repo now also includes a FastAPI backend, async worker execution, persistence, security, observability, and deployment support so it can grow toward a real product platform.

## 42. Short summary in one sentence

This project helps answer: "What is the best retrieval pipeline for my dataset, and how can I measure it properly?"

## 43. Best way to study this repo

If you are reading this project to truly understand it, do this:

1. Run the Streamlit app once.
2. Read `ui/app.py` to understand the user flow.
3. Read `runner.py` carefully because it is the core engine.
4. Read `chunkers.py`, `embedders.py`, and `retrievers.py`.
5. Then read the API and repository layers.
6. Finally read auth, worker, and settings files.

That order is usually the least confusing.

## 44. Final takeaway

If you remember only one thing, remember this:

RAG-OPS is not mainly about generating answers.
It is about **measuring retrieval quality** and helping you choose the best retrieval setup in a structured, repeatable, and increasingly production-ready way.
