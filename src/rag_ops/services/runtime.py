"""Runtime warm-up helpers used by API and worker startup."""

from __future__ import annotations

import logging

from rag_ops.settings import ServiceSettings

logger = logging.getLogger(__name__)


async def warm_runtime(settings: ServiceSettings) -> dict[str, str]:
    """Warm lightweight runtime dependencies on startup."""
    if not settings.warm_dependencies_on_startup:
        return {"status": "skipped", "detail": "startup warm-up disabled"}

    # Keep phase-one warm-up intentionally lightweight.
    import rag_ops.chunkers  # noqa: F401
    import rag_ops.embedders  # noqa: F401
    import rag_ops.retrievers  # noqa: F401

    logger.info("Runtime warm-up completed")
    return {"status": "ready", "detail": "module registries loaded"}
