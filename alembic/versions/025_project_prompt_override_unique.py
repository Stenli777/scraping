"""UNIQUE(project_id, prompt_template_id) on project_prompt_overrides

Revision ID: 025
Revises: 024
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # One row per (project, template) — current app upserts this pair; version history lives in prompt_versions.
    op.create_unique_constraint(
        "uq_project_prompt_overrides_project_template",
        "project_prompt_overrides",
        ["project_id", "prompt_template_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_project_prompt_overrides_project_template",
        "project_prompt_overrides",
        type_="unique",
    )
