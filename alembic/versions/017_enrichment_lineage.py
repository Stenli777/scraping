"""Enrichment job lineage for replay chains

Revision ID: 017
Revises: 016
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_enrichment_jobs",
        sa.Column("parent_enrichment_job_id", sa.Integer(), sa.ForeignKey("llm_enrichment_jobs.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "llm_enrichment_jobs",
        sa.Column("root_enrichment_job_id", sa.Integer(), sa.ForeignKey("llm_enrichment_jobs.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_llm_enrichment_jobs_parent", "llm_enrichment_jobs", ["parent_enrichment_job_id"])
    op.create_index("ix_llm_enrichment_jobs_root", "llm_enrichment_jobs", ["root_enrichment_job_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_enrichment_jobs_root", table_name="llm_enrichment_jobs")
    op.drop_index("ix_llm_enrichment_jobs_parent", table_name="llm_enrichment_jobs")
    op.drop_column("llm_enrichment_jobs", "root_enrichment_job_id")
    op.drop_column("llm_enrichment_jobs", "parent_enrichment_job_id")
