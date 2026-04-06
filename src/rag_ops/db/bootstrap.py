"""Database initialization helpers for service startup."""

from __future__ import annotations

from sqlalchemy import select

from rag_ops.db.models import Base, WorkspaceModel
from rag_ops.db.session import get_engine, get_session_factory
from rag_ops.settings import ServiceSettings


def initialize_database(settings: ServiceSettings) -> None:
    """Create tables and seed the default workspace when enabled."""
    if not settings.database_auto_create:
        return

    engine = get_engine(settings.database_url)
    Base.metadata.create_all(engine)

    session_factory = get_session_factory(settings)
    with session_factory() as session:
        workspace = session.execute(
            select(WorkspaceModel).where(WorkspaceModel.slug == settings.default_workspace_slug)
        ).scalar_one_or_none()
        if workspace is None:
            session.add(
                WorkspaceModel(
                    slug=settings.default_workspace_slug,
                    name=settings.default_workspace_name,
                )
            )
            session.commit()
