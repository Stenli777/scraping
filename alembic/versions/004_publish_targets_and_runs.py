"""Publish targets, publish_runs audit, crmflow24 mock target seed

Revision ID: 004
Revises: 003
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "publish_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("endpoint_url", sa.String(2048), nullable=True),
        sa.Column("auth_type", sa.String(32), server_default="none"),
        sa.Column("auth_token_env_name", sa.String(128), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("dry_run", sa.Boolean(), server_default="false"),
        sa.Column("default_status", sa.String(32), server_default="draft"),
        sa.Column("payload_format", sa.String(64), server_default="article_v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_publish_targets_project_id", "publish_targets", ["project_id"])

    op.create_table(
        "publish_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("scraping_tasks.id"), nullable=True),
        sa.Column("publish_target_id", sa.Integer(), sa.ForeignKey("publish_targets.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("dry_run", sa.Boolean(), server_default="false"),
        sa.Column("endpoint_url", sa.String(2048), nullable=True),
        sa.Column("request_payload_json", postgresql.JSONB(), nullable=True),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(256), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_publish_runs_document_id", "publish_runs", ["document_id"])
    op.create_index("ix_publish_runs_publish_target_id", "publish_runs", ["publish_target_id"])

    conn = op.get_bind()
    row = conn.execute(sa.text("SELECT id FROM projects WHERE slug = 'crmflow24'")).fetchone()
    if row:
        conn.execute(
            sa.text(
                """
                INSERT INTO publish_targets (
                  project_id, name, target_type, endpoint_url, auth_type,
                  auth_token_env_name, enabled, dry_run, default_status, payload_format
                )
                SELECT :pid, 'crmflow24-draft-mock', 'mock', NULL, 'none',
                       NULL, true, true, 'draft', 'article_v1'
                WHERE NOT EXISTS (
                  SELECT 1 FROM publish_targets WHERE project_id = :pid AND name = 'crmflow24-draft-mock'
                )
                """
            ),
            {"pid": row[0]},
        )


def downgrade() -> None:
    op.drop_index("ix_publish_runs_publish_target_id", table_name="publish_runs")
    op.drop_index("ix_publish_runs_document_id", table_name="publish_runs")
    op.drop_table("publish_runs")
    op.drop_index("ix_publish_targets_project_id", table_name="publish_targets")
    op.drop_table("publish_targets")
