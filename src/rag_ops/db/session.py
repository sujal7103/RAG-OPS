"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from rag_ops.settings import ServiceSettings, get_settings


def _normalize_sqlite_url(url: str) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    path = Path(url[len(prefix) :])
    if not path.is_absolute():
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{path}"


@lru_cache(maxsize=4)
def get_engine(database_url: str | None = None) -> Engine:
    """Create or return a cached SQLAlchemy engine."""
    settings = get_settings()
    url = _normalize_sqlite_url(database_url or settings.database_url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)


def get_session_factory(settings: ServiceSettings | None = None) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the active engine."""
    active_settings = settings or get_settings()
    return sessionmaker(bind=get_engine(active_settings.database_url), expire_on_commit=False)


async def ping_database(settings: ServiceSettings | None = None) -> bool:
    """Check whether the configured database is reachable."""
    active_settings = settings or get_settings()

    def _ping() -> bool:
        with get_engine(active_settings.database_url).connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    return await asyncio.to_thread(_ping)
