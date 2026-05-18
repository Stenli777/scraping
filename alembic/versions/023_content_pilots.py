"""Content pilots for production pilot workflow

Revision ID: 023
Revises: 022
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PILOT_STATUSES = ("draft", "active", "completed", "archived")
ITEM_STATUSES = (
    "candidate",
    "in_progress",
    "draft_created",
    "draft_reviewed",
    "public_confirmed",
    "analytics_started",
    "blocked",
    "done",
)


def upgrade() -> None:
    op.create_table(
        "content_pilots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft", index=True),
        sa.Column("target_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "slug", name="uq_content_pilots_project_slug"),
    )
    op.create_table(
        "content_pilot_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pilot_id", sa.Integer(), sa.ForeignKey("content_pilots.id", ondelete="CASCADE"), index=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"), index=True),
        sa.Column(
            "release_candidate_id",
            sa.Integer(),
            sa.ForeignKey("content_release_candidates.id", ondelete="SET NULL"),
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
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(32), nullable=False, server_default="candidate", index=True),
        sa.Column("next_action", sa.String(64), nullable=True),
        sa.Column("blockers_json", JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("pilot_id", "document_id", name="uq_content_pilot_items_pilot_document"),
    )


def downgrade() -> None:
    op.drop_table("content_pilot_items")
    op.drop_table("content_pilots")
