"""Benchmark run execution and queue submission helpers."""

from __future__ import annotations

import logging
import threading

from rag_ops.db.session import get_session_factory
from rag_ops.repositories.platform import PlatformRepository
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


def execute_benchmark_run(run_id: str, settings: ServiceSettings | None = None) -> None:
    """Execute a persisted run using the existing benchmark engine."""
    active_settings = settings or get_settings()
    session_factory = get_session_factory
    state_store = RunStateStore(active_settings)

    with session_factory(active_settings)() as session:
        repo = PlatformRepository(session, active_settings)
        execution_context = repo.get_run_execution_context(run_id)
        repo.mark_run_running(run_id)

    state_store.set_progress(run_id, progress_pct=1, stage="starting")

    def on_progress(percent: int, message: str) -> None:
        stage = message.strip()
        state_store.set_progress(run_id, progress_pct=percent, stage=stage)
        with session_factory(active_settings)() as session:
            repo = PlatformRepository(session, active_settings)
            repo.update_run_progress(run_id, progress_pct=percent, stage=stage)

    def should_cancel() -> bool:
        return state_store.is_cancel_requested(run_id)

    try:
        run_benchmark(
            documents=execution_context["documents"],
            queries=execution_context["queries"],
            ground_truth=execution_context["ground_truth"],
            chunker_names=execution_context["config"]["chunker_names"],
            embedder_names=execution_context["config"]["embedder_names"],
            retriever_names=execution_context["config"]["retriever_names"],
            top_k=execution_context["config"]["top_k"],
            progress_callback=on_progress,
            enable_disk_cache=True,
            cache_dir=ensure_directory(get_default_cache_dir()),
            persist_run_artifacts=True,
            runs_dir=ensure_directory(get_default_runs_dir()),
            cancel_callback=should_cancel,
            run_id=run_id,
        )
    except BenchmarkCancelledError:
        with session_factory(active_settings)() as session:
            repo = PlatformRepository(session, active_settings)
            repo.mark_run_cancelled(run_id)
        state_store.set_progress(run_id, progress_pct=100, stage="cancelled")
        return
    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        with session_factory(active_settings)() as session:
            repo = PlatformRepository(session, active_settings)
            repo.fail_run(run_id, str(exc))
        state_store.set_progress(run_id, progress_pct=100, stage="failed")
        return

    with session_factory(active_settings)() as session:
        repo = PlatformRepository(session, active_settings)
        repo.complete_run(run_id)
    state_store.set_progress(run_id, progress_pct=100, stage="completed")


def enqueue_benchmark_run(run_id: str, settings: ServiceSettings | None = None) -> str:
    """Enqueue a persisted run using the configured backend."""
    active_settings = settings or get_settings()
    backend = active_settings.queue_backend.lower()

    if backend in {"disabled", "none"}:
        return "disabled"

    if backend == "dramatiq":
        try:
            from rag_ops.workers.tasks import process_benchmark_run_actor

            process_benchmark_run_actor.send(run_id)
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
    return "thread"
