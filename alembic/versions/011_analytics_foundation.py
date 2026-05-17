"""Publication tracking and analytics

Revision ID: 011
Revises: 010
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "publication_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id"), nullable=False, index=True),
        sa.Column("revision_id", sa.Integer(), sa.ForeignKey("document_revisions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("publish_run_id", sa.Integer(), sa.ForeignKey("publish_runs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("external_article_id", sa.String(256), nullable=True),
        sa.Column("external_url", sa.String(2048), nullable=True),
        sa.Column("publication_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_publication_records_status", "publication_records", ["publication_status"])

    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("publication_record_id", sa.Integer(), sa.ForeignKey("publication_records.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("unique_visitors", sa.Integer(), nullable=True),
        sa.Column("avg_time_seconds", sa.Integer(), nullable=True),
        sa.Column("bounce_rate", sa.Float(), nullable=True),
        sa.Column("ctr", sa.Float(), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("conversions", sa.Integer(), nullable=True),
        sa.Column("position_avg", sa.Float(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_analytics_snapshots_date", "analytics_snapshots", ["snapshot_date"])

    op.create_table(
        "content_performance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id"), nullable=False, index=True),
        sa.Column("publication_record_id", sa.Integer(), sa.ForeignKey("publication_records.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("latest_views", sa.Integer(), nullable=True),
        sa.Column("latest_ctr", sa.Float(), nullable=True),
        sa.Column("latest_position", sa.Float(), nullable=True),
        sa.Column("latest_conversions", sa.Integer(), nullable=True),
        sa.Column("performance_score", sa.Integer(), nullable=True),
        sa.Column("trend", sa.String(16), nullable=True, server_default="unknown"),
        sa.Column("status", sa.String(16), nullable=True, server_default="average"),
        sa.Column("performance_feedback_json", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("content_performance")
    op.drop_index("ix_analytics_snapshots_date", table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")
    op.drop_index("ix_publication_records_status", table_name="publication_records")
    op.drop_table("publication_records")
