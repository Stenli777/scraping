"""Automation rules, runs, scheduler state

Revision ID: 012
Revises: 011
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false"),
        sa.Column("trigger_type", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("schedule_cron", sa.String(64), nullable=True),
        sa.Column("automation_type", sa.String(64), nullable=False),
        sa.Column("config_json", postgresql.JSONB(), nullable=True),
        sa.Column("rate_limit_per_hour", sa.Integer(), server_default="10"),
        sa.Column("max_daily_runs", sa.Integer(), server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_automation_rules_enabled", "automation_rules", ["enabled"])

    op.create_table(
        "automation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("automation_rule_id", sa.Integer(), sa.ForeignKey("automation_rules.id", ondelete="CASCADE"), index=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("affected_entities_json", postgresql.JSONB(), nullable=True),
        sa.Column("logs_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_tasks", sa.Integer(), server_default="0"),
        sa.Column("created_documents", sa.Integer(), server_default="0"),
        sa.Column("created_discoveries", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_automation_runs_status", "automation_runs", ["status"])

    op.create_table(
        "scheduler_state",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("scheduler_state")
    op.drop_index("ix_automation_runs_status", table_name="automation_runs")
    op.drop_table("automation_runs")
    op.drop_index("ix_automation_rules_enabled", table_name="automation_rules")
    op.drop_table("automation_rules")
