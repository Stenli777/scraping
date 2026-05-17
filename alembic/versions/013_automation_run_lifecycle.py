"""Automation run lifecycle fields

Revision ID: 013
Revises: 012
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("automation_runs", sa.Column("requested_by", sa.String(64), nullable=True))
    op.add_column("automation_runs", sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("automation_runs", sa.Column("locked_by", sa.String(64), nullable=True))
    op.add_column("automation_runs", sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("automation_runs", sa.Column("progress_json", postgresql.JSONB(), nullable=True))
    op.add_column("automation_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("automation_runs", sa.Column("trigger_type", sa.String(32), nullable=True))
    op.create_index("ix_automation_runs_heartbeat_at", "automation_runs", ["heartbeat_at"])


def downgrade() -> None:
    op.drop_index("ix_automation_runs_heartbeat_at", table_name="automation_runs")
    op.drop_column("automation_runs", "trigger_type")
    op.drop_column("automation_runs", "heartbeat_at")
    op.drop_column("automation_runs", "progress_json")
    op.drop_column("automation_runs", "lock_expires_at")
    op.drop_column("automation_runs", "locked_by")
    op.drop_column("automation_runs", "requested_at")
    op.drop_column("automation_runs", "requested_by")
