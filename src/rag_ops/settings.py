"""Runtime settings helpers for app, API, worker, and CLI usage."""

from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import ConfigDict, Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:
    from pydantic import BaseModel

    def _parse_env_file(path_value: str) -> dict[str, str]:
        path = Path(path_value)
        if not path.exists():
            return {}

        parsed: dict[str, str] = {}
        for raw_line in path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            parsed[key.strip()] = value.strip().strip('"').strip("'")
        return parsed

    class BaseSettings(BaseModel):
        """Lightweight fallback when pydantic-settings is unavailable."""

        model_config = ConfigDict(populate_by_name=True, extra="ignore")

        def __init__(self, **data):
            config = getattr(self.__class__, "model_config", {})
            env_file = config.get("env_file") if isinstance(config, dict) else None

            merged: dict[str, str | object] = {}
            if env_file:
                merged.update(_parse_env_file(str(env_file)))
            merged.update(os.environ)
            merged.update(data)
            super().__init__(**merged)

    def SettingsConfigDict(**kwargs):
        """Fallback SettingsConfigDict shim backed by pydantic ConfigDict."""
        defaults = {"populate_by_name": True}
        defaults.update(kwargs)
        return ConfigDict(**defaults)


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


def get_default_api_base_url() -> str:
    """Return the configured API base URL for the admin UI."""
    return os.getenv("RAG_OPS_API_BASE_URL", "").strip().rstrip("/")


def get_default_credential_key() -> str:
    """Return a persisted local credential key for development use."""
    configured = os.getenv("RAG_OPS_CREDENTIAL_KEY", "").strip()
    if configured:
        return configured

    state_dir = Path(ensure_directory(get_default_state_dir()))
    key_path = state_dir / "credential.key"
    if key_path.exists():
        return key_path.read_text().strip()

    generated = secrets.token_urlsafe(32)
    key_path.write_text(generated)
    return generated


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
    api_base_url: str = Field(default_factory=get_default_api_base_url, alias="RAG_OPS_API_BASE_URL")
    ui_api_poll_interval_seconds: float = Field(
        1.0,
        alias="RAG_OPS_UI_API_POLL_INTERVAL_SECONDS",
    )
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
    run_max_attempts: int = Field(2, alias="RAG_OPS_RUN_MAX_ATTEMPTS")
    run_retry_backoff_seconds: float = Field(
        1.0,
        alias="RAG_OPS_RUN_RETRY_BACKOFF_SECONDS",
    )
    queue_backend: str = Field("thread", alias="RAG_OPS_QUEUE_BACKEND")
    run_state_ttl_seconds: int = Field(3600, alias="RAG_OPS_RUN_STATE_TTL_SECONDS")
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
    auth_mode: str = Field("dev", alias="RAG_OPS_AUTH_MODE")
    auth_auto_provision_memberships: bool = Field(
        False,
        alias="RAG_OPS_AUTH_AUTO_PROVISION_MEMBERSHIPS",
    )
    auth_jwt_secret: str = Field("", alias="RAG_OPS_AUTH_JWT_SECRET")
    auth_jwt_algorithm: str = Field("HS256", alias="RAG_OPS_AUTH_JWT_ALGORITHM")
    auth_jwt_audience: str = Field("", alias="RAG_OPS_AUTH_JWT_AUDIENCE")
    auth_jwt_issuer: str = Field("", alias="RAG_OPS_AUTH_JWT_ISSUER")
    auth_jwt_workspace_claim: str = Field(
        "workspace_slug",
        alias="RAG_OPS_AUTH_JWT_WORKSPACE_CLAIM",
    )
    auth_jwt_role_claim: str = Field("role", alias="RAG_OPS_AUTH_JWT_ROLE_CLAIM")
    dev_default_user_email: str = Field(
        "owner@ragops.local",
        alias="RAG_OPS_DEV_DEFAULT_USER_EMAIL",
    )
    dev_default_user_name: str = Field(
        "RAG-OPS Owner",
        alias="RAG_OPS_DEV_DEFAULT_USER_NAME",
    )
    dev_default_user_role: str = Field(
        "workspace_owner",
        alias="RAG_OPS_DEV_DEFAULT_USER_ROLE",
    )
    credential_key: str = Field(
        default_factory=get_default_credential_key,
        alias="RAG_OPS_CREDENTIAL_KEY",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> ServiceSettings:
    """Return cached service settings for the current process."""
    return ServiceSettings()
