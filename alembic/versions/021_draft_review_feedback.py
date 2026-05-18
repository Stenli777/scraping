"""Draft review feedback and draft_review_status columns

Revision ID: 021
Revises: 020
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "draft_review_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "release_candidate_id",
            sa.Integer(),
            sa.ForeignKey("content_release_candidates.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "publish_run_id",
            sa.Integer(),
            sa.ForeignKey("publish_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "publication_record_id",
            sa.Integer(),
            sa.ForeignKey("publication_records.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("external_url", sa.String(2048), nullable=True),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="pending", index=True),
        sa.Column("reviewer_name", sa.String(128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("required_changes_json", postgresql.JSONB(), nullable=True),
        sa.Column("checked_public_visibility", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("checked_seo", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("checked_content", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("checked_media", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("visibility_check_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.add_column(
        "content_release_candidates",
        sa.Column("draft_review_status", sa.String(32), nullable=True, index=True),
    )
    op.add_column(
        "content_release_candidates",
        sa.Column("draft_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "publication_records",
        sa.Column("draft_review_status", sa.String(32), nullable=True, index=True),
    )
    op.add_column(
        "publication_records",
        sa.Column("draft_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "publication_records",
        sa.Column("final_operator_notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("publication_records", "final_operator_notes")
    op.drop_column("publication_records", "draft_reviewed_at")
    op.drop_column("publication_records", "draft_review_status")
    op.drop_column("content_release_candidates", "draft_reviewed_at")
    op.drop_column("content_release_candidates", "draft_review_status")
    op.drop_table("draft_review_feedback")
