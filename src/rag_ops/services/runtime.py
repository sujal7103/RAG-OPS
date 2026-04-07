"""Runtime warm-up helpers used by API and worker startup."""

from __future__ import annotations

import logging

from rag_ops.object_store import ObjectStoreClient
from rag_ops.security.auth import _resolve_oidc_jwks_url
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

    warmed_components = ["module registries loaded"]
    if settings.auth_mode.strip().lower() in {"oidc", "jwks"}:
        jwks_url = _resolve_oidc_jwks_url(settings)
        if jwks_url:
            warmed_components.append(f"auth jwks ready from {jwks_url}")
    if settings.object_store_enabled:
        ObjectStoreClient(settings).ping()
        warmed_components.append("object store probed")

    logger.info("Runtime warm-up completed")
    return {"status": "ready", "detail": ", ".join(warmed_components)}
