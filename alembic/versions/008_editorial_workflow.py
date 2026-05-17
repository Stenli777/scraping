"""Editorial workflow states, document revisions, publish revision link

Revision ID: 008
Revises: 007
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parsed_documents",
        sa.Column("editorial_status", sa.String(32), server_default="generated", nullable=False),
    )
    op.add_column("parsed_documents", sa.Column("editorial_notes", sa.Text(), nullable=True))
    op.add_column(
        "parsed_documents",
        sa.Column("operator_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "parsed_documents",
        sa.Column("operator_rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "parsed_documents",
        sa.Column("operator_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "parsed_documents",
        sa.Column("approved_for_publish", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "parsed_documents",
        sa.Column("current_revision_number", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_parsed_documents_editorial_status",
        "parsed_documents",
        ["editorial_status"],
    )

    op.create_table(
        "document_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_reference_id", sa.Integer(), nullable=True),
        sa.Column("rewrite_text", sa.Text(), nullable=True),
        sa.Column("seo_snapshot_json", postgresql.JSONB(), nullable=True),
        sa.Column("quality_snapshot_json", postgresql.JSONB(), nullable=True),
        sa.Column("editorial_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "document_id",
            "revision_number",
            name="uq_document_revisions_document_revision",
        ),
    )
    op.create_index(
        "ix_document_revisions_document_id",
        "document_revisions",
        ["document_id"],
    )

    op.add_column(
        "publish_runs",
        sa.Column(
            "document_revision_id",
            sa.Integer(),
            sa.ForeignKey("document_revisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_publish_runs_document_revision_id",
        "publish_runs",
        ["document_revision_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_publish_runs_document_revision_id", table_name="publish_runs")
    op.drop_column("publish_runs", "document_revision_id")
    op.drop_index("ix_document_revisions_document_id", table_name="document_revisions")
    op.drop_table("document_revisions")
    op.drop_index("ix_parsed_documents_editorial_status", table_name="parsed_documents")
    op.drop_column("parsed_documents", "current_revision_number")
    op.drop_column("parsed_documents", "approved_for_publish")
    op.drop_column("parsed_documents", "operator_reviewed_at")
    op.drop_column("parsed_documents", "operator_rejected_at")
    op.drop_column("parsed_documents", "operator_approved_at")
    op.drop_column("parsed_documents", "editorial_notes")
    op.drop_column("parsed_documents", "editorial_status")
