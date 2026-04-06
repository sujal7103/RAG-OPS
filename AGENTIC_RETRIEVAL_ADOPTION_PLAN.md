# Agentic Retrieval Adoption Plan For RAG-OPS

## Summary

This document captures the useful production patterns we should borrow from the `agenticretrieval` reference codebase without pulling RAG-OPS into that product's domain model.

The comparison is based on implemented code, especially:

- `memrag/api_server.py`
- `memrag/redis_cache.py`
- `memrag/router_auth_middleware.py`
- `memrag/router_security_config.py`
- `memrag/connection_pool.py`
- `memrag/redis_vector_cache.py`

At a high level:

- `agenticretrieval` is a service-style retrieval platform with a real API layer, middleware, Redis integration, startup lifecycle, and deployment topology.
- `RAG-OPS` is still a Streamlit-first benchmark product with a strong core engine, but without a proper service boundary yet.

This is an add-on to the existing RAG-OPS production roadmap, not a replacement for it.

## What Agentic Retrieval Does Well

### 1. FastAPI lifecycle and health boundaries

`memrag/api_server.py` uses an application lifespan to handle startup, warm-up, dependency initialization, and shutdown in one place. It also exposes a health endpoint early.

Useful takeaway for RAG-OPS:

- add a real API process
- initialize expensive dependencies during startup
- separate startup failures from request-time failures
- ship `/health` and `/ready` from day one

### 2. Middleware for cross-cutting concerns

`memrag/api_server.py` and `memrag/router_auth_middleware.py` treat auth, timeout control, and request logging as middleware concerns instead of mixing them into endpoint logic.

Useful takeaway for RAG-OPS:

- inject auth context through middleware
- assign request IDs centrally
- standardize request timing and error shaping
- keep business logic out of request plumbing

### 3. Thin Redis abstraction

`memrag/redis_cache.py` is simple and focused. It wraps JSON and byte operations, TTL handling, and connection setup so the rest of the app does not talk to raw Redis directly.

Useful takeaway for RAG-OPS:

- create a thin Redis client wrapper early
- keep Redis usage behind clear methods
- avoid spreading raw `redis` calls across worker and API code

### 4. Warm-up logic for expensive dependencies

`memrag/api_server.py` and `memrag/redis_vector_cache.py` both include warm-up patterns for clients and embedding models. Even when the exact logic is specific to that product, the operational idea is strong.

Useful takeaway for RAG-OPS:

- warm embedder providers and external clients at startup
- make cold starts predictable
- surface readiness separately from basic health

### 5. Client and connection management

`memrag/connection_pool.py` shows strong attention to connection reuse and lifecycle management for external systems.

Useful takeaway for RAG-OPS:

- manage database and HTTP clients deliberately
- prefer library-native pooling first
- only build custom pools if profiling proves the need

### 6. Real local deployment topology

`agenticretrieval` includes Docker Compose and a service-oriented runtime shape. That matters because it forces clear boundaries between app, cache, and infrastructure.

Useful takeaway for RAG-OPS:

- develop locally with the same core topology we want in staging
- run API, worker, Redis, Postgres, and object storage as separate services

## What RAG-OPS Should Adopt

### 1. A real FastAPI service

RAG-OPS should add a dedicated FastAPI process and move toward an API-first product shape.

The API should own:

- datasets
- benchmark configs
- runs
- artifacts
- workspace credentials

It should expose:

- `/health`
- `/ready`
- run submission and status endpoints
- dataset and config CRUD endpoints

### 2. Redis-backed job, progress, and cancel state

RAG-OPS should use Redis for:

- async job queue state
- run progress updates
- cancellation flags
- short-lived derived state

Redis should not become the source of record for benchmark history. That remains a Postgres responsibility.

### 3. Request IDs, run IDs, and structured logs

RAG-OPS should standardize structured JSON logs carrying:

- `request_id`
- `run_id`
- `workspace_id`
- `dataset_version_id`
- `stage`
- `duration_ms`

This should exist in both API and worker processes.

### 4. Storage and repository abstractions

RAG-OPS should introduce these interfaces early:

- `RunRepository`
- `DatasetStore`
- `ArtifactStore`
- `ChunkCache`
- `EmbeddingCache`

This will keep the benchmark engine reusable while storage evolves from local disk to Postgres, Redis, and object storage.

### 5. Readiness checks and startup warm-up

RAG-OPS should distinguish:

- process is alive
- dependencies are reachable
- expensive providers are ready

That means:

- `/health` for basic process status
- `/ready` for dependency readiness
- startup warm-up for key providers and caches

### 6. API-first execution

Right now Streamlit still triggers benchmark execution directly. That should change.

Target state:

- Streamlit becomes an admin/workspace console
- API accepts benchmark run requests
- worker executes the runs
- UI only polls status and renders results

## What RAG-OPS Should Not Copy

### 1. Hardcoded secrets in compose or env defaults

This is the clearest anti-pattern in the reference system. Secrets must not be baked into committed Compose files, defaults, or local examples.

RAG-OPS should keep:

- server-side secrets only
- encrypted workspace-managed provider credentials
- secret injection through environment or secret manager

### 2. One huge all-in-one API module

`memrag/api_server.py` proves the service architecture value, but it is still too large as a single module.

RAG-OPS should split API responsibilities into:

- app bootstrap
- middleware
- routes
- services
- repositories
- settings

### 3. Domain-specific graph and memory retrieval logic

RAG-OPS is a benchmark product, not a personalized memory retrieval system.

We should not import:

- graph traversal logic
- user memory caches
- subquery decomposition pipelines
- conversation-specific recall flows

### 4. Excessive request-path debug logging

Very verbose middleware debugging is helpful during troubleshooting but too noisy as the default architecture posture.

RAG-OPS should use:

- structured logs
- log levels
- targeted diagnostics

not always-on path-by-path debug spam.

### 5. Silent failure for important infrastructure paths

The thin Redis abstraction in `memrag/redis_cache.py` is useful, but some failure handling is too quiet for critical paths.

RAG-OPS should follow this rule:

- cache failures may degrade gracefully
- queue, persistence, and credential failures must fail clearly

## Concrete Changes To Pull Into RAG-OPS

1. Add a real FastAPI process. Borrow the lifecycle and health-check pattern from `agenticretrieval`, but keep the API focused on datasets, configs, runs, artifacts, and credentials.
2. Add middleware-based cross-cutting concerns. Use middleware for auth context, request timing, request IDs, and normalized error handling.
3. Add a thin Redis abstraction. Use it for queue state, run progress, cancellation flags, and short-lived derived data.
4. Add deliberate cache tiers. Keep worker-local hot cache as L1, Redis or object storage as L2, and make cache keys include dataset version, config fingerprint, and schema version.
5. Add startup warm-up and readiness checks for models and providers so cold starts are predictable.
6. Add repository and storage interfaces early: `RunRepository`, `DatasetStore`, `ArtifactStore`, `ChunkCache`, and `EmbeddingCache`.
7. Add structured observability. Replace ad hoc logging with JSON logs carrying `request_id`, `run_id`, `workspace_id`, `dataset_version_id`, `stage`, and `duration_ms`.
8. Add Docker Compose for the actual local platform: `api`, `worker`, `admin-ui`, `postgres`, `redis`, `minio`.
9. Use library-native pooling where possible. Borrow the connection-management idea, but prefer SQLAlchemy and client pools over custom pools unless profiling proves a need.
10. Keep agentic retrieval logic out of v1. Do not import subquery decomposition, graph traversal, personalized memory caches, or conversation-specific logic into the benchmark product.

## How This Changes The Existing Production Roadmap

### Phase 1

Move FastAPI, settings, lifespan, health, readiness, and request IDs to the front of the roadmap.

### Phase 2

Make Redis mandatory with async execution instead of treating it as an optional later optimization.

### Phase 3

Pull observability earlier so API and worker ship with structured logs and readiness checks from the start.

### Phase 4

Keep the same security direction, but reinforce:

- server-side secrets only
- encrypted workspace credentials
- strict workspace scoping

### Phase 5

Keep cache design generic and reproducible. Avoid product-specific semantic caches too early.

## Immediate Changes To The Existing Roadmap

### Immediate PR Order

1. `PR1`: FastAPI app, settings, lifespan, health and readiness, request IDs, Docker Compose with Postgres, Redis, and MinIO.
2. `PR2`: Postgres schema, Alembic, repositories, dataset and config persistence.
3. `PR3`: Dramatiq worker, Redis-backed queue, run status, progress, and cancel flow.
4. `PR4`: Streamlit switched to API-backed datasets, configs, and runs.
5. `PR5`: encrypted workspace credentials, RBAC, and audit events.
6. `PR6`: cache adapters, artifact storage, structured logs, metrics, and retry policy.

### Test Plan

- API boot and health/readiness checks behave correctly with and without required dependencies.
- Worker runs a benchmark end-to-end without Streamlit invoking the benchmark engine directly.
- Redis outage degrades safely for cache paths and fails clearly for queue-critical paths.
- Workspace auth blocks cross-workspace access to runs, datasets, artifacts, and secrets.
- Identical dataset/config runs hit cache, while changed dataset versions or config fingerprints do not.

## Assumptions

- This document is meant to be actionable and implementation-oriented, not just a comparison note.
- The focus is on service and platform patterns from `agenticretrieval`.
- `agenticretrieval` domain logic for personalized memory and graph retrieval is out of scope for RAG-OPS.
