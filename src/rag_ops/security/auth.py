"""Request auth resolution and workspace role helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from urllib import request as urllib_request

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

    if mode == "jwt":
        return _resolve_jwt_auth_context(session, settings, request)

    if mode in {"oidc", "jwks"}:
        return _resolve_oidc_auth_context(session, settings, request)

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


def _resolve_jwt_auth_context(
    session: Session,
    settings: ServiceSettings,
    request: Request,
) -> AuthContext:
    """Resolve a bearer JWT into an authenticated workspace context."""
    if not settings.auth_jwt_secret:
        raise AuthenticationError("JWT auth is enabled but no signing secret is configured")

    auth_header = request.headers.get("authorization", "").strip()
    if not auth_header.lower().startswith("bearer "):
        raise AuthenticationError("Bearer token is required")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise AuthenticationError("Bearer token is required")

    try:
        import jwt
    except ModuleNotFoundError as exc:
        raise AuthenticationError("PyJWT is required for JWT auth mode") from exc

    decode_kwargs = {
        "algorithms": [settings.auth_jwt_algorithm],
        "options": {"require": ["sub"]},
    }
    if settings.auth_jwt_audience:
        decode_kwargs["audience"] = settings.auth_jwt_audience
    if settings.auth_jwt_issuer:
        decode_kwargs["issuer"] = settings.auth_jwt_issuer

    try:
        claims = jwt.decode(token, settings.auth_jwt_secret, **decode_kwargs)
    except Exception as exc:
        raise AuthenticationError("Invalid bearer token") from exc

    user_email = str(claims.get("email") or claims.get("sub") or "").strip().lower()
    if not user_email:
        raise AuthenticationError("JWT token is missing an email or subject")
    user_name = str(claims.get("name") or claims.get("preferred_username") or user_email).strip()
    workspace_slug = str(
        claims.get(settings.auth_jwt_workspace_claim)
        or request.headers.get("x-rag-ops-workspace-slug", "")
        or settings.default_workspace_slug
    ).strip()
    role_claim = str(claims.get(settings.auth_jwt_role_claim, "workspace_member")).strip()

    workspace = _get_workspace(session, workspace_slug)
    user = session.execute(select(UserModel).where(UserModel.email == user_email)).scalar_one_or_none()
    if user is None:
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
        if not settings.auth_auto_provision_memberships:
            raise AuthorizationError("Workspace membership required")
        membership = MembershipModel(
            workspace_id=workspace.id,
            user_id=user.id,
            role=role_claim or "workspace_member",
        )
        session.add(membership)
        session.commit()
        session.refresh(user)
        session.refresh(workspace)
        session.refresh(membership)

    return AuthContext(
        user_id=user.id,
        user_email=user.email,
        user_name=user.display_name,
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        workspace_name=workspace.name,
        role=membership.role,
        auth_mode="jwt",
    )


def _resolve_oidc_auth_context(
    session: Session,
    settings: ServiceSettings,
    request: Request,
) -> AuthContext:
    """Resolve an external OIDC/JWKS bearer token."""
    auth_header = request.headers.get("authorization", "").strip()
    if not auth_header.lower().startswith("bearer "):
        raise AuthenticationError("Bearer token is required")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise AuthenticationError("Bearer token is required")

    try:
        import jwt
    except ModuleNotFoundError as exc:
        raise AuthenticationError("PyJWT is required for OIDC auth mode") from exc

    jwks_url = _resolve_oidc_jwks_url(settings)
    if not jwks_url:
        raise AuthenticationError("OIDC auth is enabled but no JWKS or discovery URL is configured")

    try:
        signing_key = _get_jwk_client(jwks_url).get_signing_key_from_jwt(token)
    except Exception as exc:
        raise AuthenticationError("Could not resolve a signing key for the bearer token") from exc

    decode_kwargs = {
        "algorithms": [settings.auth_jwt_algorithm],
        "options": {"require": ["sub"]},
    }
    if settings.auth_jwt_audience:
        decode_kwargs["audience"] = settings.auth_jwt_audience
    if settings.auth_jwt_issuer:
        decode_kwargs["issuer"] = settings.auth_jwt_issuer

    try:
        claims = jwt.decode(token, signing_key.key, **decode_kwargs)
    except Exception as exc:
        raise AuthenticationError("Invalid OIDC bearer token") from exc

    user_email = str(
        claims.get(settings.auth_oidc_email_claim)
        or claims.get("email")
        or claims.get("sub")
        or ""
    ).strip().lower()
    if not user_email:
        raise AuthenticationError("OIDC token is missing an email or subject")

    user_name = str(
        claims.get(settings.auth_oidc_name_claim)
        or claims.get("preferred_username")
        or user_email
    ).strip()
    workspace_slug = str(
        claims.get(settings.auth_jwt_workspace_claim)
        or request.headers.get("x-rag-ops-workspace-slug", "")
        or settings.default_workspace_slug
    ).strip()
    role_claim = str(claims.get(settings.auth_jwt_role_claim, "workspace_member")).strip()

    return _build_membership_auth_context(
        session,
        settings,
        user_email=user_email,
        user_name=user_name,
        workspace_slug=workspace_slug,
        requested_role=role_claim or "workspace_member",
        auth_mode="oidc",
    )


def _build_membership_auth_context(
    session: Session,
    settings: ServiceSettings,
    *,
    user_email: str,
    user_name: str,
    workspace_slug: str,
    requested_role: str,
    auth_mode: str,
) -> AuthContext:
    """Resolve or provision a user and workspace membership into an auth context."""
    workspace = _get_workspace(session, workspace_slug)
    user = session.execute(select(UserModel).where(UserModel.email == user_email)).scalar_one_or_none()
    if user is None:
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
        if not settings.auth_auto_provision_memberships:
            raise AuthorizationError("Workspace membership required")
        membership = MembershipModel(
            workspace_id=workspace.id,
            user_id=user.id,
            role=requested_role,
        )
        session.add(membership)
        session.commit()
        session.refresh(user)
        session.refresh(workspace)
        session.refresh(membership)

    return AuthContext(
        user_id=user.id,
        user_email=user.email,
        user_name=user.display_name,
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        workspace_name=workspace.name,
        role=membership.role,
        auth_mode=auth_mode,
    )


@lru_cache(maxsize=4)
def _get_jwk_client(jwks_url: str):
    import jwt

    return jwt.PyJWKClient(jwks_url)


def _resolve_oidc_jwks_url(settings: ServiceSettings) -> str:
    if settings.auth_oidc_jwks_url.strip():
        return settings.auth_oidc_jwks_url.strip()
    discovery_url = settings.auth_oidc_discovery_url.strip()
    if not discovery_url:
        return ""
    with urllib_request.urlopen(discovery_url, timeout=settings.dependency_timeout_seconds) as response:
        payload = response.read().decode("utf-8")
    import json

    discovery = json.loads(payload)
    return str(discovery.get("jwks_uri", "")).strip()


def _get_workspace(session: Session, workspace_slug: str) -> WorkspaceModel:
    workspace = session.execute(
        select(WorkspaceModel).where(WorkspaceModel.slug == workspace_slug)
    ).scalar_one_or_none()
    if workspace is None:
        raise AuthorizationError("Workspace access denied")
    return workspace
