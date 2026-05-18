"""Public publication confirmation fields

Revision ID: 022
Revises: 021
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("publication_records", sa.Column("public_url", sa.String(2048), nullable=True))
    op.add_column(
        "publication_records",
        sa.Column("public_visibility_status", sa.String(32), nullable=False, server_default="unknown", index=True),
    )
    op.add_column(
        "publication_records", sa.Column("public_visibility_checked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "publication_records",
        sa.Column("public_visible_in_blog", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "publication_records",
        sa.Column("public_visible_in_sitemap", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "publication_records",
        sa.Column("public_visible_in_rss", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("publication_records", sa.Column("public_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("publication_records", sa.Column("public_confirmed_by", sa.String(128), nullable=True))
    op.add_column("publication_records", sa.Column("public_confirmation_notes", sa.Text(), nullable=True))

    op.add_column(
        "content_release_candidates",
        sa.Column("public_status", sa.String(32), nullable=True, index=True),
    )
    op.add_column(
        "content_release_candidates",
        sa.Column("public_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_release_candidates", "public_confirmed_at")
    op.drop_column("content_release_candidates", "public_status")
    op.drop_column("publication_records", "public_confirmation_notes")
    op.drop_column("publication_records", "public_confirmed_by")
    op.drop_column("publication_records", "public_confirmed_at")
    op.drop_column("publication_records", "public_visible_in_rss")
    op.drop_column("publication_records", "public_visible_in_sitemap")
    op.drop_column("publication_records", "public_visible_in_blog")
    op.drop_column("publication_records", "public_visibility_checked_at")
    op.drop_column("publication_records", "public_visibility_status")
    op.drop_column("publication_records", "public_url")
