"""Health and readiness report builders."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from rag_ops.db.session import ping_database
from rag_ops.redis_client import RedisClient
from rag_ops.settings import ServiceSettings


class ComponentStatus(BaseModel):
    """Status for a single runtime dependency."""

    status: str = Field(..., description="ok, degraded, skipped, or failed")
    detail: str = Field("", description="Human-readable status detail")
    latency_ms: float | None = Field(default=None, description="Latency in milliseconds")


class HealthReport(BaseModel):
    """Response model for health and readiness endpoints."""

    status: str
    service: str
    environment: str
    timestamp: str
    components: dict[str, ComponentStatus]


async def build_health_report(settings: ServiceSettings) -> HealthReport:
    """Return a lightweight liveness report."""
    return HealthReport(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components={
            "api": ComponentStatus(status="ok", detail="process is alive"),
        },
    )


async def build_readiness_report(
    settings: ServiceSettings,
    redis_client: RedisClient,
    startup_state: dict[str, str],
) -> tuple[HealthReport, int]:
    """Return a readiness report and HTTP status code."""
    components: dict[str, ComponentStatus] = {}
    overall_status = "ok"

    start = time.perf_counter()
    try:
        await ping_database(settings)
        db_status = ComponentStatus(
            status="ok",
            detail="database reachable",
            latency_ms=(time.perf_counter() - start) * 1000,
        )
    except Exception as exc:
        overall_status = "degraded"
        db_status = ComponentStatus(
            status="failed",
            detail=f"database unreachable: {exc}",
            latency_ms=(time.perf_counter() - start) * 1000,
        )
    components["database"] = db_status

    if settings.redis_enabled:
        start = time.perf_counter()
        redis_ready = await redis_client.ping()
        if redis_ready:
            components["redis"] = ComponentStatus(
                status="ok",
                detail="redis reachable",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        else:
            overall_status = "degraded"
            components["redis"] = ComponentStatus(
                status="failed",
                detail="redis unreachable",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
    else:
        components["redis"] = ComponentStatus(status="skipped", detail="redis disabled")

    warm_status = startup_state.get("warm_status", "skipped")
    components["warmup"] = ComponentStatus(
        status="ok" if warm_status == "ready" else warm_status,
        detail=startup_state.get("warm_detail", "warm-up not executed"),
    )

    report = HealthReport(
        status=overall_status,
        service=settings.app_name,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components=components,
    )
    return report, (200 if overall_status == "ok" else 503)
