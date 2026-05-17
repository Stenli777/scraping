"""Hermes orchestration audit table

Revision ID: 009
Revises: 008
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hermes_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_kind", sa.String(64), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("parsed_documents.id"),
            nullable=True,
        ),
        sa.Column("request_payload_json", postgresql.JSONB(), nullable=True),
        sa.Column("response_payload_json", postgresql.JSONB(), nullable=True),
        sa.Column("agent_requested", sa.String(64), nullable=True),
        sa.Column("agent_used", sa.String(64), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("success", sa.Boolean(), server_default="false"),
        sa.Column("fallback_used", sa.Boolean(), server_default="false"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_hermes_runs_task_kind", "hermes_runs", ["task_kind"])
    op.create_index("ix_hermes_runs_document_id", "hermes_runs", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_hermes_runs_document_id", table_name="hermes_runs")
    op.drop_index("ix_hermes_runs_task_kind", table_name="hermes_runs")
    op.drop_table("hermes_runs")
