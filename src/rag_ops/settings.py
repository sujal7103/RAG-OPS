"""Runtime settings helpers for app and CLI usage."""

from __future__ import annotations

import os
from pathlib import Path


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

