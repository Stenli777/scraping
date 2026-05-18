"""Source quality scores and domain trust registry

Revision ID: 018
Revises: 017
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_trust_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("domain", sa.String(255), nullable=False, index=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("trust_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("trust_level", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_domain_trust_domain_project", "domain_trust_registry", ["domain", "project_id"], unique=True)

    op.create_table(
        "source_quality_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_directory_id", sa.Integer(), sa.ForeignKey("source_directories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("discovered_url_id", sa.Integer(), sa.ForeignKey("discovered_urls.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False, index=True),
        sa.Column("quality_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relevance_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trust_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("spam_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("thin_content_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_noise_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("language_detected", sa.String(16), nullable=True),
        sa.Column("strategy_allowed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("strategy_block_reason", sa.String(64), nullable=True),
        sa.Column("scoring_version", sa.String(32), nullable=False, server_default="source_quality_v1"),
        sa.Column("scoring_details_json", postgresql.JSONB(), nullable=True),
        sa.Column("manual_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_source_quality_discovered_url", "source_quality_scores", ["discovered_url_id"])




def downgrade() -> None:
    op.drop_table("source_quality_scores")
    op.drop_table("domain_trust_registry")
