"""Publish retry chains and acknowledgment fields

Revision ID: 014
Revises: 013
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "publish_runs",
        sa.Column("retry_parent_publish_run_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_publish_runs_retry_parent",
        "publish_runs",
        "publish_runs",
        ["retry_parent_publish_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_publish_runs_retry_parent",
        "publish_runs",
        ["retry_parent_publish_run_id"],
    )
    op.add_column(
        "publish_runs",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "publish_runs",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "publish_runs",
        sa.Column("last_retry_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "publish_runs",
        sa.Column("response_schema_version", sa.String(32), nullable=True),
    )
    op.add_column(
        "publish_runs",
        sa.Column("remote_status", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("publish_runs", "remote_status")
    op.drop_column("publish_runs", "response_schema_version")
    op.drop_column("publish_runs", "last_retry_error")
    op.drop_column("publish_runs", "next_retry_at")
    op.drop_column("publish_runs", "retry_count")
    op.drop_index("ix_publish_runs_retry_parent", table_name="publish_runs")
    op.drop_constraint("fk_publish_runs_retry_parent", "publish_runs", type_="foreignkey")
    op.drop_column("publish_runs", "retry_parent_publish_run_id")
