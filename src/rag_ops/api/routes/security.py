"""Security and identity endpoints for the RAG-OPS API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from rag_ops.api.dependencies import get_platform_repository
from rag_ops.repositories.platform import PlatformRepository

router = APIRouter(prefix="/v1", tags=["security"])


class ProviderCredentialCreateRequest(BaseModel):
    """Create a workspace-scoped provider credential."""

    provider: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    secret: str = Field(..., min_length=1)


@router.get("/me")
def get_current_identity(repo: PlatformRepository = Depends(get_platform_repository)):
    """Return the resolved auth context for the current request."""
    return repo.get_current_identity()


@router.get("/provider-credentials")
def list_provider_credentials(repo: PlatformRepository = Depends(get_platform_repository)):
    """List active provider credentials for the current workspace."""
    try:
        repo.require_role("workspace_admin")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"items": repo.list_provider_credentials()}


@router.post("/provider-credentials", status_code=status.HTTP_201_CREATED)
def create_provider_credential(
    payload: ProviderCredentialCreateRequest,
    repo: PlatformRepository = Depends(get_platform_repository),
):
    """Create an encrypted provider credential in the current workspace."""
    try:
        repo.require_role("workspace_admin")
        return repo.create_provider_credential(
            provider=payload.provider.strip(),
            label=payload.label.strip(),
            secret_value=payload.secret,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Credential encryption dependency is not installed",
        ) from exc


@router.delete("/provider-credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_credential(
    credential_id: str,
    repo: PlatformRepository = Depends(get_platform_repository),
):
    """Soft-delete a provider credential from the current workspace."""
    try:
        repo.require_role("workspace_admin")
        repo.delete_provider_credential(credential_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
