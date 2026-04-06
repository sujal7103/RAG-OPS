"""Repositories for datasets, configs, and benchmark runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from rag_ops.cache import fingerprint_dataset
from rag_ops.db.models import (
    BenchmarkConfigModel,
    BenchmarkRunModel,
    DatasetDocumentModel,
    DatasetModel,
    DatasetQueryModel,
    DatasetVersionModel,
    WorkspaceModel,
)
from rag_ops.models import Document, Query
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

    def __init__(self, session: Session, settings: ServiceSettings):
        self.session = session
        self.settings = settings

    def get_default_workspace(self) -> WorkspaceModel:
        """Return the seeded default workspace."""
        workspace = self.session.execute(
            select(WorkspaceModel).where(WorkspaceModel.slug == self.settings.default_workspace_slug)
        ).scalar_one()
        return workspace

    def create_dataset(
        self,
        *,
        name: str,
        documents: Sequence[Document],
        queries: Sequence[Query],
        ground_truth: dict[str, set[str]],
    ) -> dict[str, Any]:
        """Create or version a dataset within the default workspace."""
        workspace = self.get_default_workspace()
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
        return self.get_dataset(dataset.id)

    def list_datasets(self) -> list[dict[str, Any]]:
        """Return all datasets in the default workspace."""
        workspace = self.get_default_workspace()
        datasets = self.session.execute(
            select(DatasetModel)
            .where(DatasetModel.workspace_id == workspace.id)
            .options(selectinload(DatasetModel.versions))
            .order_by(DatasetModel.updated_at.desc())
        ).scalars()
        return [self._serialize_dataset_summary(dataset) for dataset in datasets]

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        """Return detailed dataset information."""
        workspace = self.get_default_workspace()
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
        workspace = self.get_default_workspace()
        config = BenchmarkConfigModel(
            workspace_id=workspace.id,
            name=name,
            fingerprint=fingerprint_config(config_json),
            config_json=config_json,
        )
        self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        return self._serialize_config(config)

    def list_configs(self) -> list[dict[str, Any]]:
        """Return all benchmark configs for the default workspace."""
        workspace = self.get_default_workspace()
        configs = self.session.execute(
            select(BenchmarkConfigModel)
            .where(BenchmarkConfigModel.workspace_id == workspace.id)
            .order_by(BenchmarkConfigModel.created_at.desc())
        ).scalars()
        return [self._serialize_config(config) for config in configs]

    def get_config(self, config_id: str) -> dict[str, Any]:
        """Return one benchmark configuration."""
        workspace = self.get_default_workspace()
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
        workspace = self.get_default_workspace()
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
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return self._serialize_run(run)

    def list_runs(self) -> list[dict[str, Any]]:
        """Return all runs for the default workspace."""
        workspace = self.get_default_workspace()
        runs = self.session.execute(
            select(BenchmarkRunModel)
            .where(BenchmarkRunModel.workspace_id == workspace.id)
            .order_by(BenchmarkRunModel.created_at.desc())
        ).scalars()
        return [self._serialize_run(run) for run in runs]

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Return a single benchmark run."""
        workspace = self.get_default_workspace()
        run = self.session.execute(
            select(BenchmarkRunModel).where(
                BenchmarkRunModel.workspace_id == workspace.id,
                BenchmarkRunModel.id == run_id,
            )
        ).scalar_one_or_none()
        if run is None:
            raise LookupError(f"Run {run_id} not found")
        return self._serialize_run(run)

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
            "error_summary": run.error_summary,
            "created_at": _serialize_datetime(run.created_at),
            "started_at": _serialize_datetime(run.started_at),
            "finished_at": _serialize_datetime(run.finished_at),
        }
