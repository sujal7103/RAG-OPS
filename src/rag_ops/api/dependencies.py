"""FastAPI dependencies for repositories and service state."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import HTTPException, Request

from rag_ops.repositories.platform import PlatformRepository
from rag_ops.security.auth import (
    AuthenticationError,
    AuthorizationError,
    resolve_request_auth_context,
)


def get_platform_repository(request: Request) -> Generator[PlatformRepository, None, None]:
    """Yield a repository bound to the current request session."""
    session = request.app.state.session_factory()
    try:
        try:
            auth_context = resolve_request_auth_context(
                session,
                request.app.state.settings,
                request,
            )
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        request.state.auth_context = auth_context
        yield PlatformRepository(session, request.app.state.settings, auth_context)
    finally:
        session.close()
