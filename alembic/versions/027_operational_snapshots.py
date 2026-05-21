"""Phase D: bounded operational snapshots for trend/history visibility."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="diagnostics"),
        sa.Column("metrics_json", JSONB(), nullable=False),
    )
    op.create_index("ix_operational_snapshots_captured_at", "operational_snapshots", ["captured_at"])


def downgrade() -> None:
    op.drop_index("ix_operational_snapshots_captured_at", table_name="operational_snapshots")
    op.drop_table("operational_snapshots")
