"""Runtime settings helpers for app, API, worker, and CLI usage."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_env_api_key(name: str) -> str:
    """Return an API key from environment variables if available."""
    return os.getenv(name, "").strip()


def get_default_cache_dir() -> str:
    """Return the cache directory configured for the current environment."""
    return os.getenv("RAG_OPS_CACHE_DIR", ".rag_ops_cache")


def get_default_runs_dir() -> str:
    """Return the run-artifact directory configured for the current environment."""
    return os.getenv("RAG_OPS_RUNS_DIR", ".rag_ops_runs")


def ensure_directory(path_value: str) -> str:
    """Ensure a directory exists and return its string path."""
    path = Path(path_value)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_default_state_dir() -> str:
    """Return the default service-state directory path."""
    return os.getenv("RAG_OPS_STATE_DIR", ".rag_ops")


def get_default_database_url() -> str:
    """Return the default database URL used by the service layer."""
    state_dir = ensure_directory(get_default_state_dir())
    return os.getenv("RAG_OPS_DATABASE_URL", f"sqlite:///{state_dir}/rag_ops.db")


class ServiceSettings(BaseSettings):
    """Configuration shared by the API, worker, and platform services."""

    app_name: str = "RAG-OPS"
    environment: str = Field("development", alias="RAG_OPS_ENV")
    log_level: str = Field("INFO", alias="RAG_OPS_LOG_LEVEL")
    json_logs: bool = Field(False, alias="RAG_OPS_JSON_LOGS")

    api_host: str = Field("0.0.0.0", alias="RAG_OPS_API_HOST")
    api_port: int = Field(8000, alias="RAG_OPS_API_PORT")
    admin_host: str = Field("0.0.0.0", alias="RAG_OPS_ADMIN_HOST")
    admin_port: int = Field(8501, alias="RAG_OPS_ADMIN_PORT")
    request_timeout_seconds: float = Field(60.0, alias="RAG_OPS_REQUEST_TIMEOUT_SECONDS")
    dependency_timeout_seconds: float = Field(
        2.0,
        alias="RAG_OPS_DEPENDENCY_TIMEOUT_SECONDS",
    )

    database_url: str = Field(default_factory=get_default_database_url, alias="RAG_OPS_DATABASE_URL")
    database_auto_create: bool = Field(True, alias="RAG_OPS_DATABASE_AUTO_CREATE")

    redis_url: str = Field("redis://localhost:6379/0", alias="RAG_OPS_REDIS_URL")
    redis_enabled: bool = Field(False, alias="RAG_OPS_REDIS_ENABLED")
    redis_socket_timeout_seconds: float = Field(
        1.0,
        alias="RAG_OPS_REDIS_SOCKET_TIMEOUT_SECONDS",
    )

    object_store_enabled: bool = Field(False, alias="RAG_OPS_OBJECT_STORE_ENABLED")
    object_store_endpoint: str = Field("http://localhost:9000", alias="RAG_OPS_OBJECT_STORE_ENDPOINT")
    object_store_bucket: str = Field("rag-ops", alias="RAG_OPS_OBJECT_STORE_BUCKET")

    worker_poll_interval_seconds: float = Field(
        2.0,
        alias="RAG_OPS_WORKER_POLL_INTERVAL_SECONDS",
    )
    warm_dependencies_on_startup: bool = Field(
        False,
        alias="RAG_OPS_WARM_DEPENDENCIES_ON_STARTUP",
    )
    default_workspace_slug: str = Field(
        "personal",
        alias="RAG_OPS_DEFAULT_WORKSPACE_SLUG",
    )
    default_workspace_name: str = Field(
        "Personal Workspace",
        alias="RAG_OPS_DEFAULT_WORKSPACE_NAME",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> ServiceSettings:
    """Return cached service settings for the current process."""
    return ServiceSettings()
