"""Thin async Redis helper for JSON and control-state operations."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from redis.asyncio import Redis

from rag_ops.settings import ServiceSettings, get_settings


class RedisClient:
    """Thin wrapper that keeps Redis access isolated from business logic."""

    def __init__(self, settings: ServiceSettings | None = None):
        self.settings = settings or get_settings()
        self._client: Redis | None = None

    @property
    def enabled(self) -> bool:
        """Return whether Redis usage is enabled for this process."""
        return self.settings.redis_enabled

    async def initialize(self) -> None:
        """Create the Redis client lazily."""
        if not self.enabled or self._client is not None:
            return
        self._client = Redis.from_url(
            self.settings.redis_url,
            encoding="utf-8",
            decode_responses=False,
            socket_timeout=self.settings.redis_socket_timeout_seconds,
            socket_connect_timeout=self.settings.redis_socket_timeout_seconds,
            health_check_interval=30,
        )

    async def ping(self) -> bool:
        """Return True if Redis is reachable."""
        if not self.enabled:
            return False
        await self.initialize()
        try:
            assert self._client is not None
            return bool(
                await asyncio.wait_for(
                    self._client.ping(),
                    timeout=self.settings.dependency_timeout_seconds,
                )
            )
        except Exception:
            return False

    async def get_json(self, key: str) -> Any | None:
        """Load JSON payload from Redis if present."""
        if not self.enabled:
            return None
        await self.initialize()
        try:
            assert self._client is not None
            data = await self._client.get(key)
            if not data:
                return None
            return json.loads(data)
        except Exception:
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Persist JSON payload in Redis."""
        if not self.enabled:
            return
        await self.initialize()
        try:
            assert self._client is not None
            payload = json.dumps(value).encode("utf-8")
            if ttl_seconds is not None and ttl_seconds > 0:
                await self._client.set(key, payload, ex=ttl_seconds)
            else:
                await self._client.set(key, payload)
        except Exception:
            return

    async def delete(self, key: str) -> None:
        """Delete a Redis key when enabled."""
        if not self.enabled:
            return
        await self.initialize()
        try:
            assert self._client is not None
            await self._client.delete(key)
        except Exception:
            return

    async def close(self) -> None:
        """Close the Redis connection if open."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
