"""Campaign planning and topic clusters

Revision ID: 015
Revises: 014
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("campaign_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("target_keywords_json", postgresql.JSONB(), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("content_goal", sa.Text(), nullable=True),
        sa.Column("publishing_goal", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_content_campaigns_project_slug", "content_campaigns", ["project_id", "slug"], unique=True)

    op.create_table(
        "topic_clusters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False, index=True),
        sa.Column("cluster_type", sa.String(32), nullable=False, server_default="informational"),
        sa.Column("primary_keyword", sa.String(255), nullable=True),
        sa.Column("secondary_keywords_json", postgresql.JSONB(), nullable=True),
        sa.Column("search_intent", sa.String(32), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_topic_clusters_project_slug", "topic_clusters", ["project_id", "slug"], unique=True)

    op.create_table(
        "document_cluster_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("topic_clusters.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("assigned_by", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_document_cluster_links_unique",
        "document_cluster_links",
        ["document_id", "cluster_id"],
        unique=True,
    )

    op.create_table(
        "campaign_document_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("content_campaigns.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("link_role", sa.String(32), nullable=False, server_default="planned"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_campaign_document_links_unique",
        "campaign_document_links",
        ["campaign_id", "document_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("campaign_document_links")
    op.drop_table("document_cluster_links")
    op.drop_table("topic_clusters")
    op.drop_table("content_campaigns")
