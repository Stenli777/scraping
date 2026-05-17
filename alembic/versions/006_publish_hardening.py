"""Publish hardening: project thresholds, publish_run fields, crmflow24 webhook target

Revision ID: 006
Revises: 005
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("minimum_review_score_for_publish", sa.Integer(), server_default="60"),
    )
    op.add_column(
        "projects",
        sa.Column("require_review_take_for_publish", sa.Boolean(), server_default="true"),
    )

    op.add_column(
        "publish_runs",
        sa.Column("payload_version", sa.String(32), server_default="article_v1"),
    )
    op.add_column(
        "publish_runs",
        sa.Column("draft_url", sa.String(2048), nullable=True),
    )
    op.add_column(
        "publish_runs",
        sa.Column("force_used", sa.Boolean(), server_default="false"),
    )

    conn = op.get_bind()
    row = conn.execute(sa.text("SELECT id FROM projects WHERE slug = 'crmflow24'")).fetchone()
    if row:
        pid = row[0]
        conn.execute(
            sa.text(
                """
                INSERT INTO publish_targets (
                  project_id, name, target_type, endpoint_url, auth_type,
                  auth_token_env_name, enabled, dry_run, default_status, payload_format
                )
                SELECT :pid, 'crmflow24-draft-webhook', 'webhook', NULL, 'bearer',
                       'CRMFLOW24_PUBLISH_TOKEN', true, true, 'draft', 'article_v1'
                WHERE NOT EXISTS (
                  SELECT 1 FROM publish_targets
                  WHERE project_id = :pid AND name = 'crmflow24-draft-webhook'
                )
                """
            ),
            {"pid": pid},
        )


def downgrade() -> None:
    op.drop_column("publish_runs", "force_used")
    op.drop_column("publish_runs", "draft_url")
    op.drop_column("publish_runs", "payload_version")
    op.drop_column("projects", "require_review_take_for_publish")
    op.drop_column("projects", "minimum_review_score_for_publish")
