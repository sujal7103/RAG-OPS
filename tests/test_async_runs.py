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


def test_execute_benchmark_run_uses_bound_workspace_credentials(monkeypatch, tmp_path: Path):
    """Worker execution should resolve stored provider credentials into API keys."""
    reset_engine_cache()
    settings = _build_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        _, dataset_version_id, config_id = _seed_dataset_and_config(client)
        credential_response = client.post(
            "/v1/provider-credentials",
            json={
                "provider": "openai",
                "label": "Workspace OpenAI",
                "secret": "sk-workspace-bound",
            },
        )
        credential_id = credential_response.json()["id"]
        run_response = client.post(
            "/v1/runs",
            json={
                "dataset_version_id": dataset_version_id,
                "benchmark_config_id": config_id,
                "credential_bindings": {"openai": credential_id},
            },
        )
        run_id = run_response.json()["id"]

    captured = {}

    def fake_run_benchmark(**kwargs):
        captured["api_keys"] = dict(kwargs.get("api_keys", {}))
        return build_results_frame([]), {}

    monkeypatch.setattr("rag_ops.services.benchmark_runs.run_benchmark", fake_run_benchmark)

    execute_benchmark_run(run_id, settings)

    assert captured["api_keys"]["openai"] == "sk-workspace-bound"


def test_execute_benchmark_run_retries_retryable_errors(monkeypatch, tmp_path: Path):
    """Retryable benchmark failures should retry and then complete."""
    reset_engine_cache()
    settings = _build_settings(
        tmp_path,
        RAG_OPS_RUN_MAX_ATTEMPTS="3",
        RAG_OPS_RUN_RETRY_BACKOFF_SECONDS="0",
    )

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

    attempts = {"count": 0}

    def flaky_run_benchmark(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ConnectionError("temporary network issue")
        return build_results_frame([]), {}

    monkeypatch.setattr("rag_ops.services.benchmark_runs.run_benchmark", flaky_run_benchmark)

    execute_benchmark_run(run_id, settings)

    with get_session_factory(settings)() as session:
        repo = PlatformRepository(session, settings)
        run_payload = repo.get_run(run_id)

    assert attempts["count"] == 2
    assert run_payload["status"] == "completed"
    assert run_payload["attempt_count"] == 2


def test_compare_and_leaderboard_endpoints_return_historical_results(monkeypatch, tmp_path: Path):
    """Historical comparison and leaderboard endpoints should expose persisted run reports."""
    reset_engine_cache()
    settings = _build_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        _, dataset_version_id, config_id = _seed_dataset_and_config(client)
        first_run = client.post(
            "/v1/runs",
            json={
                "dataset_version_id": dataset_version_id,
                "benchmark_config_id": config_id,
            },
        ).json()["id"]
        second_run = client.post(
            "/v1/runs",
            json={
                "dataset_version_id": dataset_version_id,
                "benchmark_config_id": config_id,
            },
        ).json()["id"]

    scores = iter([0.6, 0.9])

    def fake_run_benchmark(**kwargs):
        score = next(scores)
        return (
            build_results_frame(
                [
                    {
                        "chunker": "Fixed Size",
                        "embedder": "MiniLM",
                        "retriever": "Dense",
                        "precision@k": score,
                        "recall@k": score,
                        "mrr": score,
                        "ndcg@k": score,
                        "map@k": score,
                        "hit_rate@k": score,
                        "latency_ms": 10.0,
                        "num_chunks": 1,
                        "avg_chunk_size": 50.0,
                        "error": "",
                    }
                ]
            ),
            {"Fixed Size + MiniLM + Dense": []},
        )

    monkeypatch.setattr("rag_ops.services.benchmark_runs.run_benchmark", fake_run_benchmark)

    execute_benchmark_run(first_run, settings)
    execute_benchmark_run(second_run, settings)

    with TestClient(create_app(settings)) as client:
        compare_response = client.post(
            "/v1/runs/compare",
            json={"run_ids": [first_run, second_run], "metric": "recall@k"},
        )
        leaderboard_response = client.get("/v1/reports/leaderboard?metric=recall@k&limit=5")

    assert compare_response.status_code == 200
    compare_payload = compare_response.json()
    assert compare_payload["winner"]["run_id"] == second_run
    assert len(compare_payload["runs"]) == 2

    assert leaderboard_response.status_code == 200
    leaderboard_payload = leaderboard_response.json()
    assert leaderboard_payload["items"][0]["run_id"] == second_run


def test_execute_benchmark_run_persists_dead_letter_on_terminal_failure(monkeypatch, tmp_path: Path):
    """Terminal worker failures should write a dead-letter record for ops review."""
    reset_engine_cache()
    settings = _build_settings(
        tmp_path,
        RAG_OPS_RUN_MAX_ATTEMPTS="1",
        RAG_OPS_DEAD_LETTER_DIR=str(tmp_path / "dead_letters"),
    )

    with TestClient(create_app(settings)) as client:
        _, dataset_version_id, config_id = _seed_dataset_and_config(client)
        run_id = client.post(
            "/v1/runs",
            json={
                "dataset_version_id": dataset_version_id,
                "benchmark_config_id": config_id,
            },
        ).json()["id"]

    def broken_run_benchmark(**kwargs):
        raise RuntimeError("hard failure")

    monkeypatch.setattr("rag_ops.services.benchmark_runs.run_benchmark", broken_run_benchmark)

    execute_benchmark_run(run_id, settings)

    with get_session_factory(settings)() as session:
        repo = PlatformRepository(session, settings)
        run_payload = repo.get_run(run_id)

    dead_letter_path = Path(settings.dead_letter_dir) / f"{run_id}.json"
    assert run_payload["status"] == "failed"
    assert dead_letter_path.exists()


def test_execute_benchmark_run_uploads_artifacts_to_object_store(monkeypatch, tmp_path: Path):
    """When object storage is enabled, persisted artifact URIs should be rewritten to object-store paths."""
    reset_engine_cache()
    settings = _build_settings(
        tmp_path,
        RAG_OPS_OBJECT_STORE_ENABLED="true",
        RAG_OPS_OBJECT_STORE_BUCKET="rag-ops-test",
    )

    with TestClient(create_app(settings)) as client:
        _, dataset_version_id, config_id = _seed_dataset_and_config(client)
        run_id = client.post(
            "/v1/runs",
            json={
                "dataset_version_id": dataset_version_id,
                "benchmark_config_id": config_id,
            },
        ).json()["id"]

    def fake_run_benchmark(**kwargs):
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
        return build_results_frame([]), {}

    def fake_upload(self, artifact):
        return BenchmarkArtifacts(
            run_id=artifact.run_id,
            directory=f"s3://rag-ops-test/runs/{artifact.run_id}",
            summary_json=f"s3://rag-ops-test/runs/{artifact.run_id}/summary.json",
            results_csv=f"s3://rag-ops-test/runs/{artifact.run_id}/results.csv",
            results_json=f"s3://rag-ops-test/runs/{artifact.run_id}/results.json",
            per_query_json=f"s3://rag-ops-test/runs/{artifact.run_id}/per_query.json",
        )

    monkeypatch.setattr("rag_ops.services.benchmark_runs.run_benchmark", fake_run_benchmark)
    monkeypatch.setattr("rag_ops.object_store.ObjectStoreClient.upload_artifact_bundle", fake_upload)

    execute_benchmark_run(run_id, settings)

    with get_session_factory(settings)() as session:
        repo = PlatformRepository(session, settings)
        artifacts_payload = repo.list_run_artifacts(run_id)

    assert artifacts_payload["bundle"]["results_json"].startswith("s3://rag-ops-test/")
