"""Worker entrypoint for queued benchmark execution."""

from __future__ import annotations

import logging

from rag_ops.metrics_server import start_metrics_http_server
from rag_ops.observability import configure_logging
from rag_ops.settings import ServiceSettings, get_settings

logger = logging.getLogger(__name__)


def run_worker(settings: ServiceSettings | None = None) -> None:
    """Run the configured worker backend."""
    active_settings = settings or get_settings()
    configure_logging(active_settings)
    backend = active_settings.queue_backend.lower()
    if active_settings.metrics_enabled:
        start_metrics_http_server(
            host=active_settings.metrics_host,
            port=active_settings.worker_metrics_port,
        )
        logger.info(
            "Worker metrics server listening on %s:%s",
            active_settings.metrics_host,
            active_settings.worker_metrics_port,
        )
    logger.info("Starting RAG-OPS worker using backend=%s", backend)

    if backend == "dramatiq":
        try:
            from dramatiq.cli import main as dramatiq_main

            dramatiq_main(["rag_ops.workers.tasks"])
            return
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            logger.warning("Dramatiq worker unavailable, falling back to idle loop: %s", exc)

    import time

    logger.info("Worker running in idle/thread fallback mode")
    while True:
        time.sleep(active_settings.worker_poll_interval_seconds)


def main() -> None:
    """Run the worker scaffold."""
    run_worker()


if __name__ == "__main__":
    main()
