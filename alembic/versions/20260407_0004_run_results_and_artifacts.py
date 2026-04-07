"""add run results and artifacts tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0004"
down_revision = "20260407_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_result_aggregates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("benchmark_run_id", sa.String(length=36), nullable=False),
        sa.Column("config_label", sa.String(length=255), nullable=False),
        sa.Column("chunker", sa.String(length=255), nullable=False),
        sa.Column("embedder", sa.String(length=255), nullable=False),
        sa.Column("retriever", sa.String(length=255), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("num_chunks", sa.Integer(), nullable=False),
        sa.Column("avg_chunk_size", sa.Float(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["benchmark_run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_benchmark_result_aggregates_benchmark_run_id"),
        "benchmark_result_aggregates",
        ["benchmark_run_id"],
        unique=False,
    )

    op.create_table(
        "benchmark_result_per_query",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("benchmark_run_id", sa.String(length=36), nullable=False),
        sa.Column("config_label", sa.String(length=255), nullable=False),
        sa.Column("query_id", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["benchmark_run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_benchmark_result_per_query_benchmark_run_id"),
        "benchmark_result_per_query",
        ["benchmark_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_benchmark_result_per_query_config_label"),
        "benchmark_result_per_query",
        ["config_label"],
        unique=False,
    )
    op.create_index(
        op.f("ix_benchmark_result_per_query_query_id"),
        "benchmark_result_per_query",
        ["query_id"],
        unique=False,
    )

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("benchmark_run_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=120), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["benchmark_run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_artifacts_benchmark_run_id"), "artifacts", ["benchmark_run_id"], unique=False)
    op.create_index(op.f("ix_artifacts_kind"), "artifacts", ["kind"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_artifacts_kind"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_benchmark_run_id"), table_name="artifacts")
    op.drop_table("artifacts")

    op.drop_index(op.f("ix_benchmark_result_per_query_query_id"), table_name="benchmark_result_per_query")
    op.drop_index(op.f("ix_benchmark_result_per_query_config_label"), table_name="benchmark_result_per_query")
    op.drop_index(op.f("ix_benchmark_result_per_query_benchmark_run_id"), table_name="benchmark_result_per_query")
    op.drop_table("benchmark_result_per_query")

    op.drop_index(
        op.f("ix_benchmark_result_aggregates_benchmark_run_id"),
        table_name="benchmark_result_aggregates",
    )
    op.drop_table("benchmark_result_aggregates")
