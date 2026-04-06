"""SQLAlchemy models for persisted service-layer entities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def generate_id() -> str:
    """Generate a compact UUID string."""
    return str(uuid4())


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy models."""


class WorkspaceModel(Base):
    """Workspace boundary for persisted records."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    memberships: Mapped[list["MembershipModel"]] = relationship(back_populates="workspace")
    provider_credentials: Mapped[list["ProviderCredentialModel"]] = relationship(
        back_populates="workspace"
    )
    audit_events: Mapped[list["AuditEventModel"]] = relationship(back_populates="workspace")
    datasets: Mapped[list["DatasetModel"]] = relationship(back_populates="workspace")
    configs: Mapped[list["BenchmarkConfigModel"]] = relationship(back_populates="workspace")
    runs: Mapped[list["BenchmarkRunModel"]] = relationship(back_populates="workspace")


class UserModel(Base):
    """User identity used for workspace membership and audit trails."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    memberships: Mapped[list["MembershipModel"]] = relationship(back_populates="user")
    created_credentials: Mapped[list["ProviderCredentialModel"]] = relationship(
        back_populates="created_by_user"
    )
    audit_events: Mapped[list["AuditEventModel"]] = relationship(back_populates="user")


class MembershipModel(Base):
    """A user's role within a workspace."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_membership_workspace_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(64), default="workspace_member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="memberships")
    user: Mapped[UserModel] = relationship(back_populates="memberships")


class DatasetModel(Base):
    """Logical dataset tracked within a workspace."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    current_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="datasets")
    versions: Mapped[list["DatasetVersionModel"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetVersionModel.version_number",
    )


class DatasetVersionModel(Base):
    """Immutable dataset version with normalized docs and queries."""

    __tablename__ = "dataset_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(32), default="v1")
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    doc_count: Mapped[int] = mapped_column(Integer)
    query_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    dataset: Mapped[DatasetModel] = relationship(back_populates="versions")
    documents: Mapped[list["DatasetDocumentModel"]] = relationship(
        back_populates="dataset_version",
        cascade="all, delete-orphan",
    )
    queries: Mapped[list["DatasetQueryModel"]] = relationship(
        back_populates="dataset_version",
        cascade="all, delete-orphan",
    )
    runs: Mapped[list["BenchmarkRunModel"]] = relationship(back_populates="dataset_version")


class DatasetDocumentModel(Base):
    """A normalized document belonging to a dataset version."""

    __tablename__ = "dataset_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    doc_id: Mapped[str] = mapped_column(String(255))
    source_name: Mapped[str] = mapped_column(String(255), default="")
    content_text: Mapped[str] = mapped_column(Text)

    dataset_version: Mapped[DatasetVersionModel] = relationship(back_populates="documents")


class DatasetQueryModel(Base):
    """A normalized query belonging to a dataset version."""

    __tablename__ = "dataset_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    query_id: Mapped[str] = mapped_column(String(255))
    query_text: Mapped[str] = mapped_column(Text)
    relevant_doc_ids: Mapped[list[str]] = mapped_column(JSON)

    dataset_version: Mapped[DatasetVersionModel] = relationship(back_populates="queries")


class BenchmarkConfigModel(Base):
    """Persisted benchmark configuration."""

    __tablename__ = "benchmark_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="configs")
    runs: Mapped[list["BenchmarkRunModel"]] = relationship(back_populates="benchmark_config")


class BenchmarkRunModel(Base):
    """Persisted benchmark run metadata."""

    __tablename__ = "benchmark_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    benchmark_config_id: Mapped[str] = mapped_column(ForeignKey("benchmark_configs.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    latest_stage: Mapped[str] = mapped_column(String(255), default="queued")
    latest_progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="runs")
    dataset_version: Mapped[DatasetVersionModel] = relationship(back_populates="runs")
    benchmark_config: Mapped[BenchmarkConfigModel] = relationship(back_populates="runs")


class ProviderCredentialModel(Base):
    """Encrypted provider credential scoped to one workspace."""

    __tablename__ = "provider_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255))
    ciphertext: Mapped[str] = mapped_column(Text)
    key_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="provider_credentials")
    created_by_user: Mapped[UserModel] = relationship(back_populates="created_credentials")


class AuditEventModel(Base):
    """Workspace-scoped audit log entry."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str] = mapped_column(String(120))
    target_id: Mapped[str] = mapped_column(String(36))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="audit_events")
    user: Mapped[UserModel] = relationship(back_populates="audit_events")
