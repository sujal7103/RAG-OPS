"""Tests for async execution and run control flows."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rag_ops.api.app import create_app
from rag_ops.models import BenchmarkArtifacts
from rag_ops.results_frame import build_results_frame
from rag_ops.db.session import get_session_factory
from rag_ops.db.session import reset_engine_cache
from rag_ops.repositories.platform import PlatformRepository
from rag_ops.services.benchmark_runs import execute_benchmark_run
from rag_ops.settings import ServiceSettings


def _build_settings(tmp_path: Path, **overrides) -> ServiceSettings:
    db_path = tmp_path / "rag_ops_async.db"
    state_dir = tmp_path / "state"
    base = {
        "RAG_OPS_DATABASE_URL": f"sqlite:///{db_path}",
        "RAG_OPS_DATABASE_AUTO_CREATE": "true",
        "RAG_OPS_REDIS_ENABLED": "false",
        "RAG_OPS_ENV": "test",
        "RAG_OPS_QUEUE_BACKEND": "disabled",
        "RAG_OPS_STATE_DIR": str(state_dir),
        "RAG_OPS_DEFAULT_WORKSPACE_SLUG": "async-workspace",
        "RAG_OPS_DEFAULT_WORKSPACE_NAME": "Async Workspace",
    }
    base.update({key: str(value) for key, value in overrides.items()})
    return ServiceSettings(**base)


def _seed_dataset_and_config(client: TestClient) -> tuple[str, str, str]:
    dataset_response = client.post(
        "/v1/datasets",
        json={
            "name": "Async Docs",
            "documents": [
                {"doc_id": "d1", "content": "Python basics", "source": "d1.txt"},
            ],
            "queries": [
                {"query_id": "q1", "query": "What is Python?"},
            ],
            "ground_truth": {"q1": ["d1"]},
        },
    )
    dataset_payload = dataset_response.json()

    config_response = client.post(
        "/v1/configs",
        json={
            "name": "Async Config",
            "chunker_names": ["Fixed Size"],
            "embedder_names": ["MiniLM"],
            "retriever_names": ["Dense"],
            "top_k": 1,
        },
    )
    config_payload = config_response.json()
    return dataset_payload["id"], dataset_payload["latest_version"]["id"], config_payload["id"]


def test_cancel_endpoint_marks_run_cancel_requested(tmp_path: Path):
    """Cancellation requests should update run status and timestamp."""
    reset_engine_cache()
    settings = _build_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        _, dataset_version_id, config_id = _seed_dataset_and_config(client)
        run_response = client.post(
            "/v1/runs",
            json={
                "dataset_version_id": dataset_version_id,
                "benchmark_config_id": config_id,
            },
        )
        run_id = run_response.json()["id"]

        cancel_response = client.post(f"/v1/runs/{run_id}/cancel")

    assert cancel_response.status_code == 200
    payload = cancel_response.json()
    assert payload["status"] == "cancel_requested"
    assert payload["cancel_requested_at"] is not None


def test_execute_benchmark_run_updates_status(monkeypatch, tmp_path: Path):
    """Worker execution should move runs to completed and store progress."""
    reset_engine_cache()
    settings = _build_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        _, dataset_version_id, config_id = _seed_dataset_and_config(client)
        run_response = client.post(
            "/v1/runs",
            json={
                "dataset_version_id": dataset_version_id,
                "benchmark_config_id": config_id,
            },
        )
        run_id = run_response.json()["id"]

    def fake_run_benchmark(**kwargs):
        kwargs["progress_callback"](25, "Preparing test run")
        kwargs["progress_callback"](75, "Finishing test run")
        if kwargs.get("artifact_callback") is not None:
            artifact_dir = tmp_path / "runs" / kwargs["run_id"]
            artifact_dir.mkdir(parents=True, exist_ok=True)
            summary_json = artifact_dir / "summary.json"
            results_csv = artifact_dir / "results.csv"
            results_json = artifact_dir / "results.json"
            per_query_json = artifact_dir / "per_query.json"
            summary_json.write_text("{}")
            results_csv.write_text("chunker,embedder,retriever\n")
            results_json.write_text("[]")
            per_query_json.write_text("{}")
            kwargs["artifact_callback"](
                BenchmarkArtifacts(
                    run_id=kwargs["run_id"],
                    directory=str(artifact_dir),
                    summary_json=str(summary_json),
                    results_csv=str(results_csv),
                    results_json=str(results_json),
                    per_query_json=str(per_query_json),
                )
            )
        return (
            build_results_frame(
                [
                    {
                        "chunker": "Fixed Size",
                        "embedder": "MiniLM",
                        "retriever": "Dense",
                        "precision@k": 1.0,
                        "recall@k": 1.0,
                        "mrr": 1.0,
                        "ndcg@k": 1.0,
                        "map@k": 1.0,
                        "hit_rate@k": 1.0,
                        "latency_ms": 12.0,
                        "num_chunks": 1,
                        "avg_chunk_size": 13.0,
                        "error": "",
                    }
                ]
            ),
            {
                "Fixed Size + MiniLM + Dense": [
                    {
                        "query_id": "q1",
                        "query": "What is Python?",
                        "retrieved_docs": "d1",
                        "relevant_docs": "d1",
                        "hit": True,
                        "precision": 1.0,
                        "recall": 1.0,
                        "mrr": 1.0,
                    }
                ]
            },
        )

    monkeypatch.setattr("rag_ops.services.benchmark_runs.run_benchmark", fake_run_benchmark)

    execute_benchmark_run(run_id, settings)

    with get_session_factory(settings)() as session:
        repo = PlatformRepository(session, settings)
        run_payload = repo.get_run(run_id)
        results_payload = repo.get_run_results(run_id)
        artifacts_payload = repo.list_run_artifacts(run_id)

    with TestClient(create_app(settings)) as client:
        api_results_response = client.get(f"/v1/runs/{run_id}/results")
        api_artifacts_response = client.get(f"/v1/runs/{run_id}/artifacts")

    assert run_payload["status"] == "completed"
    assert run_payload["latest_progress_pct"] == 100
    assert run_payload["latest_stage"] == "completed"
    assert results_payload["items"][0]["retriever"] == "Dense"
    assert results_payload["per_query_results"]["Fixed Size + MiniLM + Dense"][0]["query_id"] == "q1"
    assert artifacts_payload["bundle"]["results_json"].endswith("results.json")
    assert api_results_response.status_code == 200
    assert api_results_response.json()["items"][0]["chunker"] == "Fixed Size"
    assert api_artifacts_response.status_code == 200
    assert api_artifacts_response.json()["bundle"]["summary_json"].endswith("summary.json")
