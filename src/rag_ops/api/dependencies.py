"""FastAPI dependencies for repositories and service state."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Request

from rag_ops.repositories.platform import PlatformRepository


def get_platform_repository(request: Request) -> Generator[PlatformRepository, None, None]:
    """Yield a repository bound to the current request session."""
    session = request.app.state.session_factory()
    try:
        yield PlatformRepository(session, request.app.state.settings)
    finally:
        session.close()
