"""Governance Phase A: force_reason, operator_touched, project trust_level."""

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publish_runs", sa.Column("force_reason", sa.Text(), nullable=True))
    op.add_column(
        "parsed_documents",
        sa.Column("operator_touched", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "parsed_documents",
        sa.Column("operator_touched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "parsed_documents",
        sa.Column("operator_touched_by", sa.String(255), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("trust_level", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("projects", "trust_level")
    op.drop_column("parsed_documents", "operator_touched_by")
    op.drop_column("parsed_documents", "operator_touched_at")
    op.drop_column("parsed_documents", "operator_touched")
    op.drop_column("publish_runs", "force_reason")
