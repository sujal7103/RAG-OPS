"""add run control fields"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0002"
down_revision = "20260407_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "benchmark_runs",
        sa.Column("latest_stage", sa.String(length=255), nullable=False, server_default="queued"),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("latest_progress_pct", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("benchmark_runs", "latest_stage", server_default=None)
    op.alter_column("benchmark_runs", "latest_progress_pct", server_default=None)


def downgrade() -> None:
    op.drop_column("benchmark_runs", "cancel_requested_at")
    op.drop_column("benchmark_runs", "latest_progress_pct")
    op.drop_column("benchmark_runs", "latest_stage")
