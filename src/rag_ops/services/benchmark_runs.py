"""Benchmark run execution and queue submission helpers."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from rag_ops.db.session import get_session_factory
from rag_ops.metrics_registry import get_metrics_registry
from rag_ops.object_store import ObjectStoreClient
from rag_ops.observability import reset_run_id, reset_workspace_id, set_run_id, set_workspace_id
from rag_ops.repositories.platform import PlatformRepository
from rag_ops.results_frame import results_frame_to_records
from rag_ops.runner import BenchmarkCancelledError, run_benchmark
from rag_ops.services.run_state import RunStateStore
from rag_ops.settings import (
    ServiceSettings,
    ensure_directory,
    get_default_cache_dir,
    get_default_runs_dir,
    get_settings,
)

logger = logging.getLogger(__name__)


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    message = str(exc).lower()
    retry_tokens = [
        "timeout",
        "temporar",
        "connection",
        "rate limit",
        "unavailable",
        "try again",
    ]
    return any(token in message for token in retry_tokens)


def _record_dead_letter(
    run_id: str,
    *,
    settings: ServiceSettings,
    execution_context: dict[str, object],
    attempt_count: int,
    error_summary: str,
) -> str | None:
    """Persist a dead-letter record for a terminally failed run."""
    if not settings.dead_letter_enabled:
        return None

    directory = Path(ensure_directory(settings.dead_letter_dir))
    path = directory / f"{run_id}.json"
    payload = {
        "run_id": run_id,
        "workspace_id": execution_context.get("workspace_id"),
        "credential_bindings": execution_context.get("credential_bindings", {}),
        "config": execution_context.get("config", {}),
        "attempt_count": attempt_count,
        "error_summary": error_summary,
        "recorded_at": time.time(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return str(path)


def execute_benchmark_run(run_id: str, settings: ServiceSettings | None = None) -> None:
    """Execute a persisted run using the existing benchmark engine."""
    active_settings = settings or get_settings()
    session_factory = get_session_factory
    state_store = RunStateStore(active_settings)
    metrics = get_metrics_registry()
    run_token = set_run_id(run_id)
    workspace_token = None
    run_started = False

    try:
        with session_factory(active_settings)() as session:
            repo = PlatformRepository(session, active_settings)
            execution_context = repo.get_run_execution_context(run_id)
        workspace_token = set_workspace_id(str(execution_context.get("workspace_id", "-")))

        started_at = time.perf_counter()
        max_attempts = max(1, active_settings.run_max_attempts)
        metrics.adjust_gauge("rag_ops_benchmark_runs_in_progress", 1.0)
        run_started = True
        state_store.set_progress(run_id, progress_pct=1, stage="starting")

        def on_progress(percent: int, message: str) -> None:
            stage = message.strip()
            state_store.set_progress(run_id, progress_pct=percent, stage=stage)
            with session_factory(active_settings)() as session:
                repo = PlatformRepository(session, active_settings)
                repo.update_run_progress(run_id, progress_pct=percent, stage=stage)

        def should_cancel() -> bool:
            return state_store.is_cancel_requested(run_id)

        for attempt_count in range(1, max_attempts + 1):
            with session_factory(active_settings)() as session:
                repo = PlatformRepository(session, active_settings)
                repo.mark_run_running(run_id, attempt_count=attempt_count)

            metrics.inc_counter("rag_ops_benchmark_run_attempts_total")
            try:
                captured_artifact = {"value": None}

                def on_artifact(artifact) -> None:
                    captured_artifact["value"] = artifact

                results_frame, per_query_results = run_benchmark(
                    documents=execution_context["documents"],
                    queries=execution_context["queries"],
                    ground_truth=execution_context["ground_truth"],
                    chunker_names=execution_context["config"]["chunker_names"],
                    embedder_names=execution_context["config"]["embedder_names"],
                    retriever_names=execution_context["config"]["retriever_names"],
                    top_k=execution_context["config"]["top_k"],
                    api_keys=execution_context.get("api_keys", {}),
                    progress_callback=on_progress,
                    enable_disk_cache=True,
                    cache_dir=ensure_directory(get_default_cache_dir()),
                    persist_run_artifacts=True,
                    runs_dir=ensure_directory(get_default_runs_dir()),
                    artifact_callback=on_artifact,
                    cancel_callback=should_cancel,
                    run_id=run_id,
                )
            except BenchmarkCancelledError:
                with session_factory(active_settings)() as session:
                    repo = PlatformRepository(session, active_settings)
                    repo.mark_run_cancelled(run_id)
                state_store.set_progress(run_id, progress_pct=100, stage="cancelled")
                metrics.inc_counter("rag_ops_benchmark_runs_total", labels={"status": "cancelled"})
                metrics.observe_histogram(
                    "rag_ops_benchmark_run_duration_seconds",
                    value=time.perf_counter() - started_at,
                    labels={"status": "cancelled"},
                )
                return
            except Exception as exc:
                if attempt_count < max_attempts and _is_retryable_error(exc):
                    logger.warning(
                        "Run %s failed on attempt %s/%s and will retry: %s",
                        run_id,
                        attempt_count,
                        max_attempts,
                        exc,
                    )
                    metrics.inc_counter("rag_ops_benchmark_retries_total")
                    with session_factory(active_settings)() as session:
                        repo = PlatformRepository(session, active_settings)
                        repo.mark_run_retrying(
                            run_id,
                            attempt_count=attempt_count,
                            error_summary=str(exc),
                        )
                    state_store.set_progress(
                        run_id,
                        progress_pct=1,
                        stage=f"retrying attempt {attempt_count + 1}",
                    )
                    time.sleep(active_settings.run_retry_backoff_seconds * attempt_count)
                    continue

                logger.exception("Run %s failed", run_id)
                dead_letter_path = _record_dead_letter(
                    run_id,
                    settings=active_settings,
                    execution_context=execution_context,
                    attempt_count=attempt_count,
                    error_summary=str(exc),
                )
                with session_factory(active_settings)() as session:
                    repo = PlatformRepository(session, active_settings)
                    repo.fail_run(run_id, str(exc))
                state_store.set_progress(run_id, progress_pct=100, stage="failed")
                metrics.inc_counter("rag_ops_benchmark_runs_total", labels={"status": "failed"})
                if dead_letter_path:
                    metrics.inc_counter("rag_ops_dead_letters_total")
                metrics.observe_histogram(
                    "rag_ops_benchmark_run_duration_seconds",
                    value=time.perf_counter() - started_at,
                    labels={"status": "failed"},
                )
                return

            uploaded_artifact = captured_artifact["value"]
            if uploaded_artifact is not None:
                uploaded_artifact = ObjectStoreClient(active_settings).upload_artifact_bundle(
                    uploaded_artifact
                )
            with session_factory(active_settings)() as session:
                repo = PlatformRepository(session, active_settings)
                repo.save_run_outputs(
                    run_id,
                    result_rows=results_frame_to_records(results_frame),
                    per_query_results=per_query_results,
                    artifact=uploaded_artifact,
                )
                repo.complete_run(run_id)
            state_store.set_progress(run_id, progress_pct=100, stage="completed")
            metrics.inc_counter("rag_ops_benchmark_runs_total", labels={"status": "completed"})
            metrics.observe_histogram(
                "rag_ops_benchmark_run_duration_seconds",
                value=time.perf_counter() - started_at,
                labels={"status": "completed"},
            )
            return
    finally:
        if run_started:
            metrics.adjust_gauge("rag_ops_benchmark_runs_in_progress", -1.0)
        state_store.clear(run_id)
        if workspace_token is not None:
            reset_workspace_id(workspace_token)
        reset_run_id(run_token)


def enqueue_benchmark_run(run_id: str, settings: ServiceSettings | None = None) -> str:
    """Enqueue a persisted run using the configured backend."""
    active_settings = settings or get_settings()
    backend = active_settings.queue_backend.lower()
    metrics = get_metrics_registry()

    if backend in {"disabled", "none"}:
        return "disabled"

    if backend == "dramatiq":
        try:
            from rag_ops.workers.tasks import process_benchmark_run_actor

            process_benchmark_run_actor.send(run_id)
            metrics.inc_counter("rag_ops_benchmark_runs_enqueued_total", labels={"backend": "dramatiq"})
            return "dramatiq"
        except Exception as exc:
            logger.warning("Falling back to thread queue for run %s: %s", run_id, exc)

    thread = threading.Thread(
        target=execute_benchmark_run,
        args=(run_id, active_settings),
        name=f"rag-ops-run-{run_id}",
        daemon=True,
    )
    thread.start()
    metrics.inc_counter("rag_ops_benchmark_runs_enqueued_total", labels={"backend": "thread"})
    return "thread"
