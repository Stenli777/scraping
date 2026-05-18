"""Canonical content groups, similarity links, rewrite lineages

Revision ID: 019
Revises: 018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canonical_content_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("canonical_slug", sa.String(512), nullable=False),
        sa.Column("canonical_title", sa.String(1024), nullable=False, server_default=""),
        sa.Column("primary_topic", sa.String(512), nullable=True),
        sa.Column("strategy_status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("duplicate_risk_level", sa.String(32), nullable=False, server_default="low"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_canonical_groups_project_slug",
        "canonical_content_groups",
        ["project_id", "canonical_slug"],
        unique=True,
    )

    op.create_table(
        "document_similarity_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id_a", sa.Integer(), sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id_b", sa.Integer(), sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "canonical_group_id",
            sa.Integer(),
            sa.ForeignKey("canonical_content_groups.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("similarity_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("similarity_type", sa.String(64), nullable=False, index=True),
        sa.Column("title_similarity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("keyword_overlap", sa.Float(), nullable=False, server_default="0"),
        sa.Column("topic_overlap", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rewrite_overlap", sa.Float(), nullable=False, server_default="0"),
        sa.Column("duplicate_risk", sa.String(32), nullable=False, server_default="low"),
        sa.Column("strategy_action", sa.String(64), nullable=True),
        sa.Column("details_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("document_id_a < document_id_b", name="ck_similarity_link_ordered_ids"),
    )
    op.create_index(
        "ix_similarity_link_pair",
        "document_similarity_links",
        ["project_id", "document_id_a", "document_id_b"],
        unique=True,
    )

    op.create_table(
        "rewrite_lineages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "root_source_document_id",
            sa.Integer(),
            sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "derived_document_id",
            sa.Integer(),
            sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("rewrite_generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("lineage_type", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_rewrite_lineage_derived_gen_type",
        "rewrite_lineages",
        ["derived_document_id", "lineage_type", "rewrite_generation"],
        unique=True,
    )

    op.add_column(
        "parsed_documents",
        sa.Column(
            "canonical_group_id",
            sa.Integer(),
            sa.ForeignKey("canonical_content_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_parsed_documents_canonical_group", "parsed_documents", ["canonical_group_id"])


def downgrade() -> None:
    op.drop_index("ix_parsed_documents_canonical_group", table_name="parsed_documents")
    op.drop_column("parsed_documents", "canonical_group_id")
    op.drop_table("rewrite_lineages")
    op.drop_table("document_similarity_links")
    op.drop_table("canonical_content_groups")
