"""Multi-project foundation: projects, llm_runs, pipeline_events, source_directories

Revision ID: 002
Revises: 001
Create Date: 2026-05-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("rewrite_profile", sa.String(64), server_default="default"),
        sa.Column("seo_profile", sa.String(64), server_default="default"),
        sa.Column("publish_mode", sa.String(32), server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)

    op.create_table(
        "source_directories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("directory_type", sa.String(32), server_default="sitemap"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_source_directories_project_id", "source_directories", ["project_id"])

    op.create_table(
        "llm_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("scraping_tasks.id"), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("model_alias", sa.String(128), nullable=False),
        sa.Column("upstream_model", sa.String(128), nullable=False),
        sa.Column("prompt_template", sa.String(128), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("finish_reason", sa.String(64), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), server_default="false"),
        sa.Column("success", sa.Boolean(), server_default="true"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_llm_runs_task_id", "llm_runs", ["task_id"])
    op.create_index("ix_llm_runs_project_id", "llm_runs", ["project_id"])

    op.create_table(
        "pipeline_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("scraping_tasks.id")),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_pipeline_events_task_id", "pipeline_events", ["task_id"])
    op.create_index("ix_pipeline_events_stage", "pipeline_events", ["stage"])

    op.add_column("scraping_tasks", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_scraping_tasks_project_id",
        "scraping_tasks",
        "projects",
        ["project_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_scraping_tasks_project_id", "scraping_tasks", type_="foreignkey")
    op.drop_column("scraping_tasks", "project_id")
    op.drop_table("pipeline_events")
    op.drop_table("llm_runs")
    op.drop_table("source_directories")
    op.drop_table("projects")
