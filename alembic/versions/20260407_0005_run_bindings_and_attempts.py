"""add run credential bindings and attempt counts"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0005"
down_revision = "20260407_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "benchmark_runs",
        sa.Column("credential_bindings_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("benchmark_runs", "credential_bindings_json", server_default=None)
    op.alter_column("benchmark_runs", "attempt_count", server_default=None)


def downgrade() -> None:
    op.drop_column("benchmark_runs", "attempt_count")
    op.drop_column("benchmark_runs", "credential_bindings_json")
