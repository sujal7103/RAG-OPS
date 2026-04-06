"""Request auth resolution and workspace role helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_ops.db.models import MembershipModel, UserModel, WorkspaceModel
from rag_ops.settings import ServiceSettings

ROLE_ORDER = {
    "workspace_member": 1,
    "workspace_admin": 2,
    "workspace_owner": 3,
}


class AuthenticationError(ValueError):
    """Raised when a request cannot be authenticated."""


class AuthorizationError(ValueError):
    """Raised when a request lacks workspace access."""


@dataclass(frozen=True)
class AuthContext:
    """Resolved identity and workspace context for one request."""

    user_id: str
    user_email: str
    user_name: str
    workspace_id: str
    workspace_slug: str
    workspace_name: str
    role: str
    auth_mode: str

    def as_dict(self) -> dict[str, str]:
        """Return a JSON-friendly auth payload."""
        return asdict(self)


def role_satisfies(current_role: str, required_role: str) -> bool:
    """Return whether the current role meets the required minimum role."""
    return ROLE_ORDER.get(current_role, 0) >= ROLE_ORDER.get(required_role, 10)


def resolve_request_auth_context(
    session: Session,
    settings: ServiceSettings,
    request: Request,
) -> AuthContext:
    """Resolve the current request into a user/workspace auth context."""
    mode = settings.auth_mode.strip().lower()
    if mode in {"none", "disabled"}:
        workspace = _get_workspace(session, settings.default_workspace_slug)
        return AuthContext(
            user_id="system",
            user_email="system@ragops.local",
            user_name="System",
            workspace_id=workspace.id,
            workspace_slug=workspace.slug,
            workspace_name=workspace.name,
            role="workspace_owner",
            auth_mode=mode,
        )

    if mode != "dev":
        raise AuthenticationError(f"Unsupported auth mode: {settings.auth_mode}")

    workspace_slug = (
        request.headers.get("x-rag-ops-workspace-slug", settings.default_workspace_slug).strip()
        or settings.default_workspace_slug
    )
    user_email = (
        request.headers.get("x-rag-ops-user-email", settings.dev_default_user_email).strip().lower()
        or settings.dev_default_user_email.lower()
    )
    user_name = (
        request.headers.get("x-rag-ops-user-name", settings.dev_default_user_name).strip()
        or settings.dev_default_user_name
    )

    workspace = _get_workspace(session, workspace_slug)
    user = session.execute(select(UserModel).where(UserModel.email == user_email)).scalar_one_or_none()
    if user is None:
        if user_email != settings.dev_default_user_email.lower():
            raise AuthenticationError("Unknown developer user")
        user = UserModel(email=user_email, display_name=user_name)
        session.add(user)
        session.flush()

    membership = session.execute(
        select(MembershipModel).where(
            MembershipModel.workspace_id == workspace.id,
            MembershipModel.user_id == user.id,
        )
    ).scalar_one_or_none()
    if membership is None:
        if (
            user_email == settings.dev_default_user_email.lower()
            and workspace.slug == settings.default_workspace_slug
        ):
            membership = MembershipModel(
                workspace_id=workspace.id,
                user_id=user.id,
                role=settings.dev_default_user_role,
            )
            session.add(membership)
            session.commit()
            session.refresh(user)
            session.refresh(workspace)
            session.refresh(membership)
        else:
            raise AuthorizationError("Workspace membership required")

    return AuthContext(
        user_id=user.id,
        user_email=user.email,
        user_name=user.display_name,
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        workspace_name=workspace.name,
        role=membership.role,
        auth_mode=mode,
    )


def _get_workspace(session: Session, workspace_slug: str) -> WorkspaceModel:
    workspace = session.execute(
        select(WorkspaceModel).where(WorkspaceModel.slug == workspace_slug)
    ).scalar_one_or_none()
    if workspace is None:
        raise AuthorizationError("Workspace access denied")
    return workspace

