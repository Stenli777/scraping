"""Content release candidates and publish_run link

Revision ID: 020
Revises: 019
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_release_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "document_revision_id",
            sa.Integer(),
            sa.ForeignKey("document_revisions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft", index=True),
        sa.Column("qa_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocking_issues_json", postgresql.JSONB(), nullable=True),
        sa.Column("warnings_json", postgresql.JSONB(), nullable=True),
        sa.Column("checklist_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "publish_target_id",
            sa.Integer(),
            sa.ForeignKey("publish_targets.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("payload_version", sa.String(32), nullable=False, server_default="article_v2"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_release_candidates_doc_status",
        "content_release_candidates",
        ["document_id", "status"],
    )

    op.add_column(
        "publish_runs",
        sa.Column(
            "release_candidate_id",
            sa.Integer(),
            sa.ForeignKey("content_release_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_publish_runs_release_candidate", "publish_runs", ["release_candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_publish_runs_release_candidate", table_name="publish_runs")
    op.drop_column("publish_runs", "release_candidate_id")
    op.drop_table("content_release_candidates")
