"""Repositories for datasets, configs, and benchmark runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from rag_ops.cache import fingerprint_dataset
from rag_ops.db.models import (
    AuditEventModel,
    BenchmarkConfigModel,
    BenchmarkRunModel,
    DatasetDocumentModel,
    DatasetModel,
    DatasetQueryModel,
    DatasetVersionModel,
    ProviderCredentialModel,
    WorkspaceModel,
)
from rag_ops.models import Document, Query, normalize_documents, normalize_ground_truth, normalize_queries
from rag_ops.security.auth import AuthContext, role_satisfies
from rag_ops.security.credentials import encrypt_secret
from rag_ops.settings import ServiceSettings


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _stable_payload(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint_config(config_json: dict[str, Any]) -> str:
    """Generate a stable configuration fingerprint."""
    return hashlib.sha256(_stable_payload(config_json).encode("utf-8")).hexdigest()[:16]


class PlatformRepository:
    """Repository facade for service-layer persisted objects."""

    def __init__(
        self,
        session: Session,
        settings: ServiceSettings,
        auth_context: AuthContext | None = None,
    ):
        self.session = session
        self.settings = settings
        self.auth_context = auth_context

    def get_workspace(self) -> WorkspaceModel:
        """Return the current workspace for this repository context."""
        if self.auth_context is not None:
            workspace = self.session.execute(
                select(WorkspaceModel).where(WorkspaceModel.id == self.auth_context.workspace_id)
            ).scalar_one_or_none()
            if workspace is not None:
                return workspace

        workspace = self.session.execute(
            select(WorkspaceModel).where(WorkspaceModel.slug == self.settings.default_workspace_slug)
        ).scalar_one()
        return workspace

    def get_current_identity(self) -> dict[str, str | None]:
        """Return the active auth context as a JSON-friendly payload."""
        workspace = self.get_workspace()
        if self.auth_context is None:
            return {
                "auth_mode": self.settings.auth_mode,
                "user_id": None,
                "user_email": None,
                "user_name": None,
                "workspace_id": workspace.id,
                "workspace_slug": workspace.slug,
                "workspace_name": workspace.name,
                "role": "workspace_owner",
            }
        return self.auth_context.as_dict()

    def require_role(self, minimum_role: str) -> None:
        """Ensure the current auth context meets the required workspace role."""
        current_role = self.auth_context.role if self.auth_context is not None else "workspace_owner"
        if not role_satisfies(current_role, minimum_role):
            raise PermissionError(
                f"Role {current_role} does not have access to this operation"
            )

    def create_dataset(
        self,
        *,
        name: str,
        documents: Sequence[Document],
        queries: Sequence[Query],
        ground_truth: dict[str, set[str]],
    ) -> dict[str, Any]:
        """Create or version a dataset within the default workspace."""
        workspace = self.get_workspace()
        dataset = self.session.execute(
            select(DatasetModel)
            .where(DatasetModel.workspace_id == workspace.id, DatasetModel.name == name)
            .options(selectinload(DatasetModel.versions))
        ).scalar_one_or_none()

        dataset_fingerprint = fingerprint_dataset(documents, queries, ground_truth)
        if dataset is None:
            dataset = DatasetModel(
                workspace_id=workspace.id,
                name=name,
                current_fingerprint=dataset_fingerprint,
            )
            self.session.add(dataset)
            self.session.flush()
            next_version_number = 1
        else:
            dataset.current_fingerprint = dataset_fingerprint
            next_version_number = len(dataset.versions) + 1

        version = DatasetVersionModel(
            dataset_id=dataset.id,
            version_number=next_version_number,
            schema_version="v1",
            fingerprint=dataset_fingerprint,
            doc_count=len(documents),
            query_count=len(queries),
        )
        self.session.add(version)
        self.session.flush()

        self.session.add_all(
            [
                DatasetDocumentModel(
                    dataset_version_id=version.id,
                    doc_id=document.doc_id,
                    source_name=document.source,
                    content_text=document.content,
                )
                for document in documents
            ]
        )
        self.session.add_all(
            [
                DatasetQueryModel(
                    dataset_version_id=version.id,
                    query_id=query.query_id,
                    query_text=query.query,
                    relevant_doc_ids=sorted(ground_truth[query.query_id]),
                )
                for query in queries
            ]
        )

        self.session.commit()
        self.session.refresh(dataset)
        self.session.refresh(version)
        self._record_audit_event(
            action="dataset.created",
            target_type="dataset",
            target_id=dataset.id,
            metadata={
                "dataset_name": dataset.name,
                "dataset_version_id": version.id,
                "version_number": version.version_number,
            },
        )
        self.session.commit()
        return self.get_dataset(dataset.id)

    def list_datasets(self) -> list[dict[str, Any]]:
        """Return all datasets in the default workspace."""
        workspace = self.get_workspace()
        datasets = self.session.execute(
            select(DatasetModel)
            .where(DatasetModel.workspace_id == workspace.id)
            .options(selectinload(DatasetModel.versions))
            .order_by(DatasetModel.updated_at.desc())
        ).scalars()
        return [self._serialize_dataset_summary(dataset) for dataset in datasets]

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        """Return detailed dataset information."""
        workspace = self.get_workspace()
        dataset = self.session.execute(
            select(DatasetModel)
            .where(DatasetModel.workspace_id == workspace.id, DatasetModel.id == dataset_id)
            .options(
                selectinload(DatasetModel.versions).selectinload(DatasetVersionModel.documents),
                selectinload(DatasetModel.versions).selectinload(DatasetVersionModel.queries),
            )
        ).scalar_one_or_none()
        if dataset is None:
            raise LookupError(f"Dataset {dataset_id} not found")
        return self._serialize_dataset_detail(dataset)

    def create_config(self, *, name: str, config_json: dict[str, Any]) -> dict[str, Any]:
        """Persist a benchmark configuration."""
        workspace = self.get_workspace()
        config = BenchmarkConfigModel(
            workspace_id=workspace.id,
            name=name,
            fingerprint=fingerprint_config(config_json),
            config_json=config_json,
        )
        self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        self._record_audit_event(
            action="config.created",
            target_type="benchmark_config",
            target_id=config.id,
            metadata={"config_name": config.name, "fingerprint": config.fingerprint},
        )
        self.session.commit()
        return self._serialize_config(config)

    def list_configs(self) -> list[dict[str, Any]]:
        """Return all benchmark configs for the default workspace."""
        workspace = self.get_workspace()
        configs = self.session.execute(
            select(BenchmarkConfigModel)
            .where(BenchmarkConfigModel.workspace_id == workspace.id)
            .order_by(BenchmarkConfigModel.created_at.desc())
        ).scalars()
        return [self._serialize_config(config) for config in configs]

    def get_config(self, config_id: str) -> dict[str, Any]:
        """Return one benchmark configuration."""
        workspace = self.get_workspace()
        config = self.session.execute(
            select(BenchmarkConfigModel).where(
                BenchmarkConfigModel.workspace_id == workspace.id,
                BenchmarkConfigModel.id == config_id,
            )
        ).scalar_one_or_none()
        if config is None:
            raise LookupError(f"Config {config_id} not found")
        return self._serialize_config(config)

    def create_run(self, *, dataset_version_id: str, benchmark_config_id: str) -> dict[str, Any]:
        """Create a queued benchmark run."""
        workspace = self.get_workspace()
        dataset_version = self.session.execute(
            select(DatasetVersionModel)
            .join(DatasetModel)
            .where(
                DatasetVersionModel.id == dataset_version_id,
                DatasetModel.workspace_id == workspace.id,
            )
        ).scalar_one_or_none()
        if dataset_version is None:
            raise LookupError(f"Dataset version {dataset_version_id} not found")

        config = self.session.execute(
            select(BenchmarkConfigModel).where(
                BenchmarkConfigModel.workspace_id == workspace.id,
                BenchmarkConfigModel.id == benchmark_config_id,
            )
        ).scalar_one_or_none()
        if config is None:
            raise LookupError(f"Config {benchmark_config_id} not found")

        run = BenchmarkRunModel(
            workspace_id=workspace.id,
            dataset_version_id=dataset_version.id,
            benchmark_config_id=config.id,
            status="queued",
            latest_stage="queued",
            latest_progress_pct=0,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        self._record_audit_event(
            action="run.created",
            target_type="benchmark_run",
            target_id=run.id,
            metadata={
                "dataset_version_id": dataset_version.id,
                "benchmark_config_id": config.id,
            },
        )
        self.session.commit()
        return self._serialize_run(run)

    def get_run_execution_context(self, run_id: str) -> dict[str, Any]:
        """Return the persisted inputs needed to execute a benchmark run."""
        statement = (
            select(BenchmarkRunModel)
            .where(BenchmarkRunModel.id == run_id)
            .options(
                selectinload(BenchmarkRunModel.dataset_version).selectinload(
                    DatasetVersionModel.documents
                ),
                selectinload(BenchmarkRunModel.dataset_version).selectinload(
                    DatasetVersionModel.queries
                ),
                selectinload(BenchmarkRunModel.benchmark_config),
            )
        )
        if self.auth_context is not None:
            statement = statement.where(BenchmarkRunModel.workspace_id == self.auth_context.workspace_id)
        run = self.session.execute(statement).scalar_one_or_none()
        if run is None:
            raise LookupError(f"Run {run_id} not found")

        dataset_version = run.dataset_version
        documents = normalize_documents(
            [
                {
                    "doc_id": document.doc_id,
                    "content": document.content_text,
                    "source": document.source_name,
                }
                for document in dataset_version.documents
            ]
        )
        queries = normalize_queries(
            [
                {
                    "query_id": query.query_id,
                    "query": query.query_text,
                }
                for query in dataset_version.queries
            ]
        )
        ground_truth = normalize_ground_truth(
            {
                query.query_id: set(query.relevant_doc_ids)
                for query in dataset_version.queries
            }
        )
        return {
            "run_id": run.id,
            "documents": documents,
            "queries": queries,
            "ground_truth": ground_truth,
            "config": dict(run.benchmark_config.config_json),
        }

    def update_run_progress(self, run_id: str, *, progress_pct: int, stage: str) -> dict[str, Any]:
        """Persist progress updates for a run."""
        run = self._get_run_model(run_id, enforce_workspace=self.auth_context is not None)
        run.latest_progress_pct = progress_pct
        run.latest_stage = stage
        self.session.commit()
        self.session.refresh(run)
        return self._serialize_run(run)

    def mark_run_running(self, run_id: str) -> dict[str, Any]:
        """Transition a run to running."""
        run = self._get_run_model(run_id, enforce_workspace=self.auth_context is not None)
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        if run.latest_progress_pct == 0:
            run.latest_progress_pct = 1
        if run.latest_stage == "queued":
            run.latest_stage = "starting"
        self.session.commit()
        self.session.refresh(run)
        return self._serialize_run(run)

    def complete_run(self, run_id: str) -> dict[str, Any]:
        """Mark a run as completed."""
        run = self._get_run_model(run_id, enforce_workspace=self.auth_context is not None)
        run.status = "completed"
        run.latest_stage = "completed"
        run.latest_progress_pct = 100
        run.finished_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(run)
        return self._serialize_run(run)

    def fail_run(self, run_id: str, error_summary: str) -> dict[str, Any]:
        """Mark a run as failed."""
        run = self._get_run_model(run_id, enforce_workspace=self.auth_context is not None)
        run.status = "failed"
        run.error_summary = error_summary
        run.finished_at = datetime.now(timezone.utc)
        if run.latest_stage == "queued":
            run.latest_stage = "failed"
        self.session.commit()
        self.session.refresh(run)
        return self._serialize_run(run)

    def request_cancel(self, run_id: str) -> dict[str, Any]:
        """Mark a run as cancellation requested."""
        run = self._get_run_model(run_id)
        run.cancel_requested_at = datetime.now(timezone.utc)
        if run.status == "queued":
            run.status = "cancel_requested"
        self.session.commit()
        self.session.refresh(run)
        self._record_audit_event(
            action="run.cancel_requested",
            target_type="benchmark_run",
            target_id=run.id,
            metadata={"status": run.status},
        )
        self.session.commit()
        return self._serialize_run(run)

    def mark_run_cancelled(self, run_id: str) -> dict[str, Any]:
        """Mark a run as cancelled."""
        run = self._get_run_model(run_id, enforce_workspace=self.auth_context is not None)
        run.status = "cancelled"
        run.latest_stage = "cancelled"
        run.finished_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(run)
        return self._serialize_run(run)

    def list_runs(self) -> list[dict[str, Any]]:
        """Return all runs for the default workspace."""
        workspace = self.get_workspace()
        runs = self.session.execute(
            select(BenchmarkRunModel)
            .where(BenchmarkRunModel.workspace_id == workspace.id)
            .order_by(BenchmarkRunModel.created_at.desc())
        ).scalars()
        return [self._serialize_run(run) for run in runs]

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Return a single benchmark run."""
        return self._serialize_run(self._get_run_model(run_id))

    def _get_run_model(self, run_id: str, *, enforce_workspace: bool = True) -> BenchmarkRunModel:
        statement = select(BenchmarkRunModel).where(BenchmarkRunModel.id == run_id)
        if enforce_workspace:
            workspace = self.get_workspace()
            statement = statement.where(BenchmarkRunModel.workspace_id == workspace.id)
        run = self.session.execute(statement).scalar_one_or_none()
        if run is None:
            raise LookupError(f"Run {run_id} not found")
        return run

    def list_provider_credentials(self) -> list[dict[str, Any]]:
        """Return active provider credentials for the current workspace."""
        workspace = self.get_workspace()
        credentials = self.session.execute(
            select(ProviderCredentialModel)
            .where(
                ProviderCredentialModel.workspace_id == workspace.id,
                ProviderCredentialModel.deleted_at.is_(None),
            )
            .order_by(ProviderCredentialModel.created_at.desc())
        ).scalars()
        return [self._serialize_provider_credential(item) for item in credentials]

    def create_provider_credential(
        self,
        *,
        provider: str,
        label: str,
        secret_value: str,
    ) -> dict[str, Any]:
        """Create an encrypted workspace-scoped provider credential."""
        if self.auth_context is None:
            raise PermissionError("Provider credentials require an authenticated workspace context")

        workspace = self.get_workspace()
        ciphertext, key_id = encrypt_secret(secret_value, self.settings.credential_key)
        credential = ProviderCredentialModel(
            workspace_id=workspace.id,
            created_by_user_id=self.auth_context.user_id,
            provider=provider,
            label=label,
            ciphertext=ciphertext,
            key_id=key_id,
        )
        self.session.add(credential)
        self.session.commit()
        self.session.refresh(credential)
        self._record_audit_event(
            action="provider_credential.created",
            target_type="provider_credential",
            target_id=credential.id,
            metadata={"provider": provider, "label": label},
        )
        self.session.commit()
        return self._serialize_provider_credential(credential)

    def delete_provider_credential(self, credential_id: str) -> None:
        """Soft-delete a provider credential within the active workspace."""
        workspace = self.get_workspace()
        credential = self.session.execute(
            select(ProviderCredentialModel).where(
                ProviderCredentialModel.workspace_id == workspace.id,
                ProviderCredentialModel.id == credential_id,
                ProviderCredentialModel.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if credential is None:
            raise LookupError(f"Provider credential {credential_id} not found")

        credential.deleted_at = datetime.now(timezone.utc)
        self.session.commit()
        self._record_audit_event(
            action="provider_credential.deleted",
            target_type="provider_credential",
            target_id=credential.id,
            metadata={"provider": credential.provider, "label": credential.label},
        )
        self.session.commit()

    def _record_audit_event(
        self,
        *,
        action: str,
        target_type: str,
        target_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist a workspace-scoped audit event when an auth context is available."""
        if self.auth_context is None:
            return
        self.session.add(
            AuditEventModel(
                workspace_id=self.auth_context.workspace_id,
                user_id=self.auth_context.user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                metadata_json=metadata or {},
            )
        )

    def _serialize_dataset_summary(self, dataset: DatasetModel) -> dict[str, Any]:
        versions = sorted(dataset.versions, key=lambda item: item.version_number)
        latest = versions[-1] if versions else None
        return {
            "id": dataset.id,
            "workspace_id": dataset.workspace_id,
            "name": dataset.name,
            "current_fingerprint": dataset.current_fingerprint,
            "created_at": _serialize_datetime(dataset.created_at),
            "updated_at": _serialize_datetime(dataset.updated_at),
            "version_count": len(versions),
            "latest_version": self._serialize_dataset_version(latest) if latest else None,
        }

    def _serialize_dataset_detail(self, dataset: DatasetModel) -> dict[str, Any]:
        summary = self._serialize_dataset_summary(dataset)
        versions = sorted(dataset.versions, key=lambda item: item.version_number)
        summary["versions"] = [self._serialize_dataset_version(version) for version in versions]
        return summary

    def _serialize_dataset_version(self, version: DatasetVersionModel | None) -> dict[str, Any] | None:
        if version is None:
            return None
        return {
            "id": version.id,
            "dataset_id": version.dataset_id,
            "version_number": version.version_number,
            "schema_version": version.schema_version,
            "fingerprint": version.fingerprint,
            "doc_count": version.doc_count,
            "query_count": version.query_count,
            "created_at": _serialize_datetime(version.created_at),
            "documents": [
                {
                    "doc_id": document.doc_id,
                    "source": document.source_name,
                    "content": document.content_text,
                }
                for document in getattr(version, "documents", [])
            ],
            "queries": [
                {
                    "query_id": query.query_id,
                    "query": query.query_text,
                    "relevant_doc_ids": list(query.relevant_doc_ids),
                }
                for query in getattr(version, "queries", [])
            ],
        }

    def _serialize_config(self, config: BenchmarkConfigModel) -> dict[str, Any]:
        return {
            "id": config.id,
            "workspace_id": config.workspace_id,
            "name": config.name,
            "fingerprint": config.fingerprint,
            "config": dict(config.config_json),
            "created_at": _serialize_datetime(config.created_at),
        }

    def _serialize_run(self, run: BenchmarkRunModel) -> dict[str, Any]:
        return {
            "id": run.id,
            "workspace_id": run.workspace_id,
            "dataset_version_id": run.dataset_version_id,
            "benchmark_config_id": run.benchmark_config_id,
            "status": run.status,
            "latest_stage": run.latest_stage,
            "latest_progress_pct": run.latest_progress_pct,
            "error_summary": run.error_summary,
            "created_at": _serialize_datetime(run.created_at),
            "started_at": _serialize_datetime(run.started_at),
            "finished_at": _serialize_datetime(run.finished_at),
            "cancel_requested_at": _serialize_datetime(run.cancel_requested_at),
        }

    def _serialize_provider_credential(self, credential: ProviderCredentialModel) -> dict[str, Any]:
        return {
            "id": credential.id,
            "workspace_id": credential.workspace_id,
            "provider": credential.provider,
            "label": credential.label,
            "key_id": credential.key_id,
            "created_by_user_id": credential.created_by_user_id,
            "created_at": _serialize_datetime(credential.created_at),
            "updated_at": _serialize_datetime(credential.updated_at),
            "deleted_at": _serialize_datetime(credential.deleted_at),
        }
