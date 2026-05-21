"""Operational incidents — bounded incident memory (Ops Stability Phase)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(48), nullable=False, index=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("summary", sa.String(512), nullable=False),
        sa.Column("context_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ref_type", sa.String(32), nullable=True),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_operational_incidents_created_at", "operational_incidents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_operational_incidents_created_at", table_name="operational_incidents")
    op.drop_table("operational_incidents")
