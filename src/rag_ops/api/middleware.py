"""Shared middleware for the RAG-OPS API."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from rag_ops.metrics_registry import get_metrics_registry
from rag_ops.observability import reset_request_id, set_request_id
from rag_ops.settings import ServiceSettings

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign request IDs and track request timing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        token = set_request_id(request_id)
        request.state.request_id = request_id
        start = time.perf_counter()
        metrics = get_metrics_registry()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            response.headers["x-request-id"] = request_id
            response.headers["x-process-time-ms"] = f"{duration_ms:.2f}"
            metrics.inc_counter(
                "rag_ops_http_requests_total",
                labels={
                    "method": request.method,
                    "path": request.url.path,
                    "status": str(response.status_code),
                },
            )
            metrics.observe_histogram(
                "rag_ops_http_request_duration_seconds",
                value=duration_ms / 1000.0,
                labels={"method": request.method, "path": request.url.path},
            )
            auth_context = getattr(request.state, "auth_context", None)
            logger.info(
                "%s %s completed in %.2fms",
                request.method,
                request.url.path,
                duration_ms,
                extra={
                    "workspace_id": getattr(auth_context, "workspace_id", "-"),
                },
            )
            return response
        finally:
            reset_request_id(token)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Enforce a global request timeout."""

    def __init__(self, app, settings: ServiceSettings) -> None:
        super().__init__(app)
        self._timeout = settings.request_timeout_seconds

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await asyncio.wait_for(call_next(request), timeout=self._timeout)
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Request processing timeout") from exc
