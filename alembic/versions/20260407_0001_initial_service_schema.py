"""initial service schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspaces_slug"), "workspaces", ["slug"], unique=True)

    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("current_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_datasets_name"), "datasets", ["name"], unique=False)
    op.create_index(op.f("ix_datasets_workspace_id"), "datasets", ["workspace_id"], unique=False)

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("doc_count", sa.Integer(), nullable=False),
        sa.Column("query_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dataset_versions_dataset_id"), "dataset_versions", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_dataset_versions_fingerprint"), "dataset_versions", ["fingerprint"], unique=False)

    op.create_table(
        "dataset_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_version_id", sa.String(length=36), nullable=False),
        sa.Column("doc_id", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dataset_documents_dataset_version_id"), "dataset_documents", ["dataset_version_id"], unique=False)

    op.create_table(
        "dataset_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_version_id", sa.String(length=36), nullable=False),
        sa.Column("query_id", sa.String(length=255), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("relevant_doc_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dataset_queries_dataset_version_id"), "dataset_queries", ["dataset_version_id"], unique=False)

    op.create_table(
        "benchmark_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_benchmark_configs_fingerprint"), "benchmark_configs", ["fingerprint"], unique=False)
    op.create_index(op.f("ix_benchmark_configs_workspace_id"), "benchmark_configs", ["workspace_id"], unique=False)

    op.create_table(
        "benchmark_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_version_id", sa.String(length=36), nullable=False),
        sa.Column("benchmark_config_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["benchmark_config_id"], ["benchmark_configs.id"]),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_benchmark_runs_benchmark_config_id"), "benchmark_runs", ["benchmark_config_id"], unique=False)
    op.create_index(op.f("ix_benchmark_runs_dataset_version_id"), "benchmark_runs", ["dataset_version_id"], unique=False)
    op.create_index(op.f("ix_benchmark_runs_status"), "benchmark_runs", ["status"], unique=False)
    op.create_index(op.f("ix_benchmark_runs_workspace_id"), "benchmark_runs", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_benchmark_runs_workspace_id"), table_name="benchmark_runs")
    op.drop_index(op.f("ix_benchmark_runs_status"), table_name="benchmark_runs")
    op.drop_index(op.f("ix_benchmark_runs_dataset_version_id"), table_name="benchmark_runs")
    op.drop_index(op.f("ix_benchmark_runs_benchmark_config_id"), table_name="benchmark_runs")
    op.drop_table("benchmark_runs")

    op.drop_index(op.f("ix_benchmark_configs_workspace_id"), table_name="benchmark_configs")
    op.drop_index(op.f("ix_benchmark_configs_fingerprint"), table_name="benchmark_configs")
    op.drop_table("benchmark_configs")

    op.drop_index(op.f("ix_dataset_queries_dataset_version_id"), table_name="dataset_queries")
    op.drop_table("dataset_queries")

    op.drop_index(op.f("ix_dataset_documents_dataset_version_id"), table_name="dataset_documents")
    op.drop_table("dataset_documents")

    op.drop_index(op.f("ix_dataset_versions_fingerprint"), table_name="dataset_versions")
    op.drop_index(op.f("ix_dataset_versions_dataset_id"), table_name="dataset_versions")
    op.drop_table("dataset_versions")

    op.drop_index(op.f("ix_datasets_workspace_id"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_name"), table_name="datasets")
    op.drop_table("datasets")

    op.drop_index(op.f("ix_workspaces_slug"), table_name="workspaces")
    op.drop_table("workspaces")
