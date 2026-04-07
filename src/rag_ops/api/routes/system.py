"""System endpoints for health, readiness, and root metadata."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from rag_ops.metrics_registry import get_metrics_registry
from rag_ops.services.health import build_health_report, build_readiness_report

router = APIRouter(tags=["system"])


@router.get("/")
async def root(request: Request) -> dict[str, str]:
    """Return basic API metadata."""
    settings = request.app.state.settings
    return {
        "service": settings.app_name,
        "environment": settings.environment,
        "status": "running",
    }


@router.get("/health")
async def health(request: Request):
    """Return a basic liveness report."""
    settings = request.app.state.settings
    report = await build_health_report(settings)
    return report.model_dump()


@router.get("/ready")
async def ready(request: Request):
    """Return dependency readiness for the API process."""
    settings = request.app.state.settings
    redis_client = request.app.state.redis_client
    startup_state = request.app.state.startup_state
    report, status_code = await build_readiness_report(settings, redis_client, startup_state)
    return JSONResponse(status_code=status_code, content=report.model_dump())


@router.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Return a Prometheus-style metrics snapshot."""
    registry = get_metrics_registry()
    return PlainTextResponse(registry.render_prometheus(), media_type="text/plain; version=0.0.4")
