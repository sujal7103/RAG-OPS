"""Progress and cancel-state storage for benchmark runs."""

from __future__ import annotations

import json
from typing import Any

import redis

from rag_ops.settings import ServiceSettings, get_settings

_memory_progress: dict[str, dict[str, Any]] = {}
_memory_cancelled: set[str] = set()


class RunStateStore:
    """Store run progress and cancel flags in Redis with an in-memory fallback."""

    def __init__(self, settings: ServiceSettings | None = None):
        self.settings = settings or get_settings()
        self._client: redis.Redis | None = None

    @property
    def enabled(self) -> bool:
        return self.settings.redis_enabled

    def _get_client(self) -> redis.Redis | None:
        if not self.enabled:
            return None
        if self._client is None:
            self._client = redis.Redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=self.settings.redis_socket_timeout_seconds,
                socket_connect_timeout=self.settings.redis_socket_timeout_seconds,
                health_check_interval=30,
            )
        return self._client

    def _progress_key(self, run_id: str) -> str:
        return f"run-progress:{run_id}"

    def _cancel_key(self, run_id: str) -> str:
        return f"run-cancel:{run_id}"

    def set_progress(self, run_id: str, *, progress_pct: int, stage: str) -> None:
        payload = {"run_id": run_id, "progress_pct": progress_pct, "stage": stage}
        client = self._get_client()
        if client is None:
            _memory_progress[run_id] = payload
            return
        try:
            client.set(
                self._progress_key(run_id),
                json.dumps(payload),
                ex=self.settings.run_state_ttl_seconds,
            )
        except Exception:
            _memory_progress[run_id] = payload

    def get_progress(self, run_id: str) -> dict[str, Any] | None:
        client = self._get_client()
        if client is None:
            return _memory_progress.get(run_id)
        try:
            data = client.get(self._progress_key(run_id))
        except Exception:
            return _memory_progress.get(run_id)
        if not data:
            return None
        return json.loads(data)

    def request_cancel(self, run_id: str) -> None:
        client = self._get_client()
        if client is None:
            _memory_cancelled.add(run_id)
            return
        try:
            client.set(self._cancel_key(run_id), "1", ex=self.settings.run_state_ttl_seconds)
        except Exception:
            _memory_cancelled.add(run_id)

    def is_cancel_requested(self, run_id: str) -> bool:
        client = self._get_client()
        if client is None:
            return run_id in _memory_cancelled
        try:
            return bool(client.exists(self._cancel_key(run_id)))
        except Exception:
            return run_id in _memory_cancelled

    def clear(self, run_id: str) -> None:
        client = self._get_client()
        if client is None:
            _memory_progress.pop(run_id, None)
            _memory_cancelled.discard(run_id)
            return
        try:
            client.delete(self._progress_key(run_id), self._cancel_key(run_id))
        except Exception:
            _memory_progress.pop(run_id, None)
            _memory_cancelled.discard(run_id)
