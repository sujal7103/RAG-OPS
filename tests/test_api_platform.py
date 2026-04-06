"""Tests for persisted platform endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rag_ops.api.app import create_app
from rag_ops.db.session import reset_engine_cache
from rag_ops.settings import ServiceSettings


def _build_settings(tmp_path: Path, **overrides) -> ServiceSettings:
    db_path = tmp_path / "rag_ops_platform.db"
    state_dir = tmp_path / "state"
    base = {
        "RAG_OPS_DATABASE_URL": f"sqlite:///{db_path}",
        "RAG_OPS_DATABASE_AUTO_CREATE": "true",
        "RAG_OPS_REDIS_ENABLED": "false",
        "RAG_OPS_ENV": "test",
        "RAG_OPS_QUEUE_BACKEND": "disabled",
        "RAG_OPS_STATE_DIR": str(state_dir),
        "RAG_OPS_DEFAULT_WORKSPACE_SLUG": "test-workspace",
        "RAG_OPS_DEFAULT_WORKSPACE_NAME": "Test Workspace",
    }
    base.update({key: str(value) for key, value in overrides.items()})
    return ServiceSettings(**base)


def test_dataset_config_and_run_flow(tmp_path: Path):
    """Datasets, configs, and runs should persist through the service API."""
    reset_engine_cache()
    settings = _build_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        dataset_response = client.post(
            "/v1/datasets",
            json={
                "name": "Python Docs",
                "documents": [
                    {
                        "doc_id": "doc-1",
                        "content": "Python uses indentation to define code blocks.",
                        "source": "doc-1.md",
                    },
                    {
                        "doc_id": "doc-2",
                        "content": "FastAPI uses type hints for request validation.",
                        "source": "doc-2.md",
                    },
                ],
                "queries": [
                    {"query_id": "q1", "query": "How does FastAPI validate requests?"},
                ],
                "ground_truth": {"q1": ["doc-2"]},
            },
        )

        assert dataset_response.status_code == 201
        dataset_payload = dataset_response.json()
        dataset_id = dataset_payload["id"]
        dataset_version_id = dataset_payload["latest_version"]["id"]
        assert dataset_payload["version_count"] == 1

        listed_datasets = client.get("/v1/datasets")
        assert listed_datasets.status_code == 200
        assert listed_datasets.json()["items"][0]["id"] == dataset_id

        detailed_dataset = client.get(f"/v1/datasets/{dataset_id}")
        assert detailed_dataset.status_code == 200
        assert detailed_dataset.json()["versions"][0]["queries"][0]["query_id"] == "q1"

        config_response = client.post(
            "/v1/configs",
            json={
                "name": "Baseline Config",
                "chunker_names": ["Fixed Size"],
                "embedder_names": ["MiniLM"],
                "retriever_names": ["Dense"],
                "top_k": 3,
            },
        )
        assert config_response.status_code == 201
        config_payload = config_response.json()
        config_id = config_payload["id"]
        assert config_payload["config"]["combination_count"] == 1

        listed_configs = client.get("/v1/configs")
        assert listed_configs.status_code == 200
        assert listed_configs.json()["items"][0]["id"] == config_id

        run_response = client.post(
            "/v1/runs",
            json={
                "dataset_version_id": dataset_version_id,
                "benchmark_config_id": config_id,
            },
        )
        assert run_response.status_code == 201
        run_payload = run_response.json()
        run_id = run_payload["id"]
        assert run_payload["status"] == "queued"
        assert run_payload["queue_backend"] == "disabled"

        listed_runs = client.get("/v1/runs")
        assert listed_runs.status_code == 200
        assert listed_runs.json()["items"][0]["id"] == run_id

        detailed_run = client.get(f"/v1/runs/{run_id}")
        assert detailed_run.status_code == 200
        assert detailed_run.json()["benchmark_config_id"] == config_id


def test_run_creation_requires_existing_references(tmp_path: Path):
    """Creating a run with unknown references should return a 404."""
    reset_engine_cache()
    settings = _build_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/runs",
            json={
                "dataset_version_id": "missing-version",
                "benchmark_config_id": "missing-config",
            },
        )

    assert response.status_code == 404
