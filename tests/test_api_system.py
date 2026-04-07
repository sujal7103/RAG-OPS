"""Tests for the FastAPI service foundation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from rag_ops.api.app import create_app
from rag_ops.metrics_registry import get_metrics_registry
from rag_ops.settings import ServiceSettings


def _build_settings(**overrides) -> ServiceSettings:
    base = {
        "RAG_OPS_DATABASE_URL": "sqlite:///./.rag_ops/test_api.db",
        "RAG_OPS_DATABASE_AUTO_CREATE": "true",
        "RAG_OPS_REDIS_ENABLED": "false",
        "RAG_OPS_ENV": "test",
        "RAG_OPS_STATE_DIR": ".rag_ops/test_api_state",
    }
    base.update({key: str(value) for key, value in overrides.items()})
    return ServiceSettings(**base)


def test_health_endpoint_reports_liveness():
    """The API should expose a simple liveness endpoint."""
    with TestClient(create_app(_build_settings())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "RAG-OPS"
    assert payload["components"]["api"]["status"] == "ok"


def test_ready_endpoint_reports_readiness_without_redis():
    """Readiness should succeed with SQLite and Redis disabled."""
    with TestClient(create_app(_build_settings())) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["components"]["database"]["status"] == "ok"
    assert payload["components"]["redis"]["status"] == "skipped"


def test_request_context_headers_are_returned():
    """The API should return the request ID and processing time headers."""
    with TestClient(create_app(_build_settings())) as client:
        response = client.get("/", headers={"x-request-id": "req-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-123"
    assert "x-process-time-ms" in response.headers


def test_metrics_endpoint_exposes_prometheus_snapshot():
    """The API should expose process metrics in Prometheus text format."""
    get_metrics_registry().reset()

    with TestClient(create_app(_build_settings())) as client:
        client.get("/")
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "rag_ops_http_requests_total" in response.text
    assert "rag_ops_http_request_duration_seconds" in response.text
