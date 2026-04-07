# RAG-OPS Deployment Guide

## Production shape

RAG-OPS now supports a practical production-style topology:

- `api` for FastAPI routes and metrics
- `worker` for async benchmark execution
- `admin-ui` for the Streamlit admin console
- `postgres` as the system of record
- `redis` for queue and run-state coordination
- `minio` or another S3-compatible store for artifact persistence
- `prometheus` and `grafana` for monitoring

## Authentication

Use `RAG_OPS_AUTH_MODE=oidc` in staging and production.

Provide either:

- `RAG_OPS_AUTH_OIDC_DISCOVERY_URL`
- or `RAG_OPS_AUTH_OIDC_JWKS_URL`

Also set:

- `RAG_OPS_AUTH_JWT_ISSUER`
- `RAG_OPS_AUTH_JWT_AUDIENCE`

Workspace and role claims default to:

- `workspace_slug`
- `role`

Those can be changed with:

- `RAG_OPS_AUTH_JWT_WORKSPACE_CLAIM`
- `RAG_OPS_AUTH_JWT_ROLE_CLAIM`

## Credential key rotation

Provider credentials are encrypted with the active key from the keyring.

Recommended settings:

- `RAG_OPS_CREDENTIAL_ACTIVE_KEY_ID=v2`
- `RAG_OPS_CREDENTIAL_KEYS_JSON={"v1":"old-key","v2":"new-key"}`

Rotation flow:

1. Add the new key to `RAG_OPS_CREDENTIAL_KEYS_JSON`
2. Switch `RAG_OPS_CREDENTIAL_ACTIVE_KEY_ID` to the new key
3. Use the admin UI or `POST /v1/provider-credentials/{id}/rotate` to re-encrypt stored credentials
4. Remove the old key only after all credentials have been rotated

## Artifacts

Set these to move run artifacts into object storage:

- `RAG_OPS_OBJECT_STORE_ENABLED=true`
- `RAG_OPS_OBJECT_STORE_ENDPOINT=...`
- `RAG_OPS_OBJECT_STORE_BUCKET=rag-ops`
- `RAG_OPS_OBJECT_STORE_ACCESS_KEY=...`
- `RAG_OPS_OBJECT_STORE_SECRET_KEY=...`

Completed runs still produce local files first, then the worker uploads the artifact bundle and persists `s3://...` URIs.

## Monitoring

Bring the stack up with:

```bash
docker compose --env-file .env.staging.example up --build
```

Endpoints:

- API health: `http://localhost:8000/health`
- API readiness: `http://localhost:8000/ready`
- API metrics: `http://localhost:8000/metrics`
- Worker metrics: `http://localhost:9101/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## Backups

Back up these components:

- Postgres volume
- MinIO or S3 bucket
- `.env` or secret manager values
- credential keyring values used in `RAG_OPS_CREDENTIAL_KEYS_JSON`

Suggested cadence:

- Postgres daily snapshot
- object-store versioning enabled
- config/secrets backup on every rotation

## Smoke checks

Run these before promoting a release:

```bash
pytest -q
python3 -m compileall app.py src tests alembic
```

After deployment:

1. Check `/health`
2. Check `/ready`
3. Confirm Prometheus can scrape API and worker metrics
4. Create a provider credential in the admin UI
5. Run a benchmark and confirm artifacts persist
6. Compare two completed runs from the historical reports UI
