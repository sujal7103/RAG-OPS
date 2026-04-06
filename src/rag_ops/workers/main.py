"""Phase-one worker scaffold for the RAG-OPS service platform."""

from __future__ import annotations

import asyncio
import logging

from rag_ops.observability import configure_logging
from rag_ops.redis_client import RedisClient
from rag_ops.settings import ServiceSettings, get_settings

logger = logging.getLogger(__name__)


async def run_worker(settings: ServiceSettings | None = None) -> None:
    """Run the worker scaffold loop until interrupted."""
    active_settings = settings or get_settings()
    configure_logging(active_settings)
    redis_client = RedisClient(active_settings)

    logger.info("Starting RAG-OPS worker scaffold")
    if active_settings.redis_enabled:
        redis_ready = await redis_client.ping()
        logger.info("Worker Redis connectivity: %s", "ready" if redis_ready else "unavailable")
    else:
        logger.info("Worker Redis disabled; running in scaffold mode")

    try:
        while True:
            await asyncio.sleep(active_settings.worker_poll_interval_seconds)
    finally:
        await redis_client.close()
        logger.info("Stopped RAG-OPS worker scaffold")


def main() -> None:
    """Run the worker scaffold."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
