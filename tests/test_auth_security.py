"""Tests for auth context, workspace security, and provider credentials."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import jwt
from sqlalchemy import select

from rag_ops.api.app import create_app
from rag_ops.db.models import (
    AuditEventModel,
    MembershipModel,
    ProviderCredentialModel,
    UserModel,
    WorkspaceModel,
)
from rag_ops.db.session import get_session_factory
from rag_ops.db.session import reset_engine_cache
from rag_ops.security.auth import _get_jwk_client
from rag_ops.security.credentials import decrypt_secret
from rag_ops.settings import ServiceSettings


def _build_settings(tmp_path: Path, **overrides) -> ServiceSettings:
    db_path = tmp_path / "rag_ops_security.db"
    state_dir = tmp_path / "state"
    base = {
        "RAG_OPS_DATABASE_URL": f"sqlite:///{db_path}",
        "RAG_OPS_DATABASE_AUTO_CREATE": "true",
        "RAG_OPS_REDIS_ENABLED": "false",
        "RAG_OPS_ENV": "test",
        "RAG_OPS_QUEUE_BACKEND": "disabled",
        "RAG_OPS_STATE_DIR": str(state_dir),
        "RAG_OPS_DEFAULT_WORKSPACE_SLUG": "personal",
        "RAG_OPS_DEFAULT_WORKSPACE_NAME": "Personal Workspace",
        "RAG_OPS_AUTH_MODE": "dev",
    }
    base.update({key: str(value) for key, value in overrides.items()})
    return ServiceSettings(**base)


def _seed_dataset(client: TestClient) -> str:
    response = client.post(
        "/v1/datasets",
        json={
            "name": "Security Docs",
            "documents": [{"doc_id": "doc-1", "content": "Auth scoped data", "source": "doc-1.txt"}],
            "queries": [{"query_id": "q1", "query": "What is auth?"}],
            "ground_truth": {"q1": ["doc-1"]},
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_me_endpoint_returns_seeded_dev_identity(tmp_path: Path):
    """The dev auth mode should expose the default seeded user and workspace."""
    reset_engine_cache()
    settings = _build_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_email"] == settings.dev_default_user_email.lower()
    assert payload["workspace_slug"] == settings.default_workspace_slug
    assert payload["role"] == settings.dev_default_user_role


def test_provider_credentials_crud_and_audit_events(tmp_path: Path):
    """Admin users should be able to manage encrypted workspace credentials."""
    reset_engine_cache()
    settings = _build_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        create_response = client.post(
            "/v1/provider-credentials",
            json={
                "provider": "openai",
                "label": "Primary OpenAI Key",
                "secret": "sk-test-123456",
            },
        )
        assert create_response.status_code == 201
        payload = create_response.json()
        credential_id = payload["id"]
        assert payload["provider"] == "openai"
        assert payload["label"] == "Primary OpenAI Key"
        assert "secret" not in payload
        assert "ciphertext" not in payload

        list_response = client.get("/v1/provider-credentials")
        assert list_response.status_code == 200
        assert list_response.json()["items"][0]["id"] == credential_id

        delete_response = client.delete(f"/v1/provider-credentials/{credential_id}")
        assert delete_response.status_code == 204

        empty_response = client.get("/v1/provider-credentials")
        assert empty_response.status_code == 200
        assert empty_response.json()["items"] == []

    with get_session_factory(settings)() as session:
        stored_credential = session.execute(select(ProviderCredentialModel)).scalar_one()
        assert stored_credential.ciphertext != "sk-test-123456"
        assert decrypt_secret(
            stored_credential.ciphertext,
            settings,
            key_id=stored_credential.key_id,
        ) == "sk-test-123456"
        assert stored_credential.deleted_at is not None

        audit_actions = [
            event.action
            for event in session.execute(select(AuditEventModel).order_by(AuditEventModel.created_at)).scalars()
        ]

    assert audit_actions == [
        "provider_credential.created",
        "provider_credential.deleted",
    ]


def test_provider_credential_rotation_uses_active_keyring_key(tmp_path: Path):
    """Stored credentials should rotate cleanly onto a new active key."""
    reset_engine_cache()
    settings = _build_settings(
        tmp_path,
        RAG_OPS_CREDENTIAL_ACTIVE_KEY_ID="v1",
        RAG_OPS_CREDENTIAL_KEYS_JSON='{"v1":"old-key-material-1234567890","v2":"new-key-material-0987654321"}',
    )

    with TestClient(create_app(settings)) as client:
        create_response = client.post(
            "/v1/provider-credentials",
            json={
                "provider": "openai",
                "label": "Rotate Me",
                "secret": "sk-rotate-me",
            },
        )
        credential_id = create_response.json()["id"]

    rotated_settings = _build_settings(
        tmp_path,
        RAG_OPS_CREDENTIAL_ACTIVE_KEY_ID="v2",
        RAG_OPS_CREDENTIAL_KEYS_JSON='{"v1":"old-key-material-1234567890","v2":"new-key-material-0987654321"}',
    )

    with TestClient(create_app(rotated_settings)) as client:
        rotate_response = client.post(f"/v1/provider-credentials/{credential_id}/rotate")

    assert rotate_response.status_code == 200
    payload = rotate_response.json()
    assert payload["key_id"] == "v2"
    assert payload["needs_rotation"] is False

    with get_session_factory(rotated_settings)() as session:
        stored_credential = session.execute(select(ProviderCredentialModel)).scalar_one()
        assert decrypt_secret(
            stored_credential.ciphertext,
            rotated_settings,
            key_id=stored_credential.key_id,
        ) == "sk-rotate-me"


def test_member_cannot_manage_provider_credentials(tmp_path: Path):
    """Workspace members should not have admin-level secret management access."""
    reset_engine_cache()
    settings = _build_settings(tmp_path, RAG_OPS_DEV_DEFAULT_USER_ROLE="workspace_member")

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/provider-credentials",
            json={
                "provider": "openai",
                "label": "Blocked Key",
                "secret": "sk-blocked",
            },
        )

    assert response.status_code == 403


def test_workspace_scoping_hides_other_workspace_resources(tmp_path: Path):
    """Users should only see datasets from workspaces they belong to."""
    reset_engine_cache()
    settings = _build_settings(tmp_path)

    with TestClient(create_app(settings)) as client:
        dataset_id = _seed_dataset(client)

        with get_session_factory(settings)() as session:
            workspace = WorkspaceModel(slug="team-b", name="Team B")
            user = UserModel(email="member@team-b.local", display_name="Team B Member")
            session.add(workspace)
            session.add(user)
            session.flush()
            session.add(
                MembershipModel(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role="workspace_member",
                )
            )
            session.commit()

        headers = {
            "x-rag-ops-user-email": "member@team-b.local",
            "x-rag-ops-workspace-slug": "team-b",
        }
        list_response = client.get("/v1/datasets", headers=headers)
        detail_response = client.get(f"/v1/datasets/{dataset_id}", headers=headers)
        denied_response = client.get(
            "/v1/datasets",
            headers={
                "x-rag-ops-user-email": "member@team-b.local",
                "x-rag-ops-workspace-slug": "personal",
            },
        )

    assert list_response.status_code == 200
    assert list_response.json()["items"] == []
    assert detail_response.status_code == 404
    assert denied_response.status_code == 403


def test_jwt_auth_mode_accepts_bearer_token_and_membership(tmp_path: Path):
    """JWT auth mode should resolve users and workspaces from bearer tokens."""
    reset_engine_cache()
    settings = _build_settings(
        tmp_path,
        RAG_OPS_AUTH_MODE="jwt",
        RAG_OPS_AUTH_JWT_SECRET="super-secret-key-for-jwt-tests-123",
        RAG_OPS_AUTH_AUTO_PROVISION_MEMBERSHIPS="true",
    )

    token = jwt.encode(
        {
            "sub": "user-123",
            "email": "jwt-user@ragops.local",
            "name": "JWT User",
            "workspace_slug": "personal",
            "role": "workspace_admin",
        },
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )

    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/v1/me",
            headers={"authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_mode"] == "jwt"
    assert payload["user_email"] == "jwt-user@ragops.local"
    assert payload["role"] == "workspace_admin"


def test_oidc_auth_mode_accepts_jwks_signed_bearer_token(monkeypatch, tmp_path: Path):
    """OIDC mode should validate bearer tokens through the configured JWKS client."""
    reset_engine_cache()
    _get_jwk_client.cache_clear()
    settings = _build_settings(
        tmp_path,
        RAG_OPS_AUTH_MODE="oidc",
        RAG_OPS_AUTH_OIDC_JWKS_URL="https://issuer.example/.well-known/jwks.json",
        RAG_OPS_AUTH_JWT_ISSUER="https://issuer.example/",
        RAG_OPS_AUTH_JWT_AUDIENCE="rag-ops",
        RAG_OPS_AUTH_AUTO_PROVISION_MEMBERSHIPS="true",
    )

    token = jwt.encode(
        {
            "sub": "oidc-user-123",
            "email": "oidc-user@ragops.local",
            "name": "OIDC User",
            "iss": settings.auth_jwt_issuer,
            "aud": settings.auth_jwt_audience,
            "workspace_slug": "personal",
            "role": "workspace_admin",
        },
        "oidc-test-secret-key-material-1234567890",
        algorithm=settings.auth_jwt_algorithm,
    )

    class FakeSigningKey:
        key = "oidc-test-secret-key-material-1234567890"

    class FakeJwkClient:
        def __init__(self, url: str) -> None:
            self.url = url

        def get_signing_key_from_jwt(self, token_value: str):
            assert token_value == token
            assert self.url == settings.auth_oidc_jwks_url
            return FakeSigningKey()

    monkeypatch.setattr(jwt, "PyJWKClient", FakeJwkClient)

    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/me", headers={"authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_mode"] == "oidc"
    assert payload["user_email"] == "oidc-user@ragops.local"
    assert payload["role"] == "workspace_admin"
