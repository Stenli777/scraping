"""Media assets and jobs

Revision ID: 010
Revises: 009
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id"), nullable=False, index=True),
        sa.Column("revision_id", sa.Integer(), sa.ForeignKey("document_revisions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("storage_path", sa.String(1024), nullable=True),
        sa.Column("original_url", sa.String(2048), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("alt_text", sa.String(512), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_media_assets_status", "media_assets", ["status"])
    op.create_index("ix_media_assets_media_type", "media_assets", ["media_type"])

    op.create_table(
        "media_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id"), nullable=False, index=True),
        sa.Column("revision_id", sa.Integer(), sa.ForeignKey("document_revisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("media_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("response_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_media_jobs_status", "media_jobs", ["status"])

    op.add_column(
        "publish_runs",
        sa.Column("preview_media_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("publish_runs", "preview_media_asset_id")
    op.drop_index("ix_media_jobs_status", table_name="media_jobs")
    op.drop_table("media_jobs")
    op.drop_index("ix_media_assets_media_type", table_name="media_assets")
    op.drop_index("ix_media_assets_status", table_name="media_assets")
    op.drop_table("media_assets")
