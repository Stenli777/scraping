"""Prompt templates, versions, overrides, content quality scores

Revision ID: 007
Revises: 006
Create Date: 2026-05-17
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _prompt_payload(system: str, user: str) -> str:
    return json.dumps({"system": system, "user": user}, ensure_ascii=False)


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_kind", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_prompt_templates_key", "prompt_templates", ["key"], unique=True)

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "prompt_template_id",
            sa.Integer(),
            sa.ForeignKey("prompt_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(128), server_default="seed"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_prompt_versions_template_id", "prompt_versions", ["prompt_template_id"])

    op.create_table(
        "project_prompt_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "prompt_template_id",
            sa.Integer(),
            sa.ForeignKey("prompt_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "prompt_version_id",
            sa.Integer(),
            sa.ForeignKey("prompt_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_project_prompt_overrides_project", "project_prompt_overrides", ["project_id"])

    op.create_table(
        "content_quality_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("scraping_tasks.id"), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("llm_run_id", sa.Integer(), sa.ForeignKey("llm_runs.id"), nullable=True),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("readability_score", sa.Integer(), nullable=True),
        sa.Column("seo_score", sa.Integer(), nullable=True),
        sa.Column("factual_consistency_score", sa.Integer(), nullable=True),
        sa.Column("structure_score", sa.Integer(), nullable=True),
        sa.Column("usefulness_score", sa.Integer(), nullable=True),
        sa.Column("spamminess_score", sa.Integer(), nullable=True),
        sa.Column("risks_json", postgresql.JSONB(), nullable=True),
        sa.Column("recommendations_json", postgresql.JSONB(), nullable=True),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_content_quality_scores_document_id", "content_quality_scores", ["document_id"])
    op.create_index("ix_content_quality_scores_verdict", "content_quality_scores", ["verdict"])

    from app.llm import prompts as p

    quality_system = """Ты главный редактор контент-фабрики. Оцени готовую статью после rewrite и SEO.
Отвечай ТОЛЬКО валидным JSON без markdown-обёртки."""
    quality_user = """Оцени качество статьи для публикации как draft. Верни JSON:
- overall_score (integer 0-100)
- readability_score (integer 0-100)
- seo_score (integer 0-100)
- factual_consistency_score (integer 0-100)
- structure_score (integer 0-100)
- usefulness_score (integer 0-100)
- spamminess_score (integer 0-100, выше = больше спама/воды)
- risks (array of strings)
- recommendations (array of strings)
- verdict (string): approved | needs_revision | rejected

{profile_block}

SEO title: {seo_title}
Slug: {slug}
URL: {source_url}

Текст статьи:
---
{content}
---"""

    seeds = [
        (
            "review_article",
            "Review article",
            "Content gate before rewrite",
            "review",
            "v1",
            _prompt_payload(p.REVIEW_ARTICLE_V1_SYSTEM, p.REVIEW_ARTICLE_V1_USER),
        ),
        (
            "rewrite_article",
            "Rewrite article",
            "Rewrite clean text to markdown article",
            "rewrite",
            "v1",
            _prompt_payload(p.REWRITE_ARTICLE_V1_SYSTEM, p.REWRITE_ARTICLE_V1_USER),
        ),
        (
            "seo_enrich",
            "SEO enrich",
            "SEO metadata generation",
            "seo",
            "v1",
            _prompt_payload(p.SEO_ENRICH_V1_SYSTEM, p.SEO_ENRICH_V1_USER),
        ),
        (
            "quality_review",
            "Quality review",
            "Post-rewrite editorial quality score",
            "quality",
            "v1",
            _prompt_payload(quality_system, quality_user),
        ),
    ]

    conn = op.get_bind()
    for key, name, desc, task_kind, version, content in seeds:
        conn.execute(
            sa.text(
                """
                INSERT INTO prompt_templates (key, name, description, task_kind, enabled)
                VALUES (:key, :name, :desc, :kind, true)
                ON CONFLICT (key) DO NOTHING
                """
            ),
            {"key": key, "name": name, "desc": desc, "kind": task_kind},
        )
        row = conn.execute(
            sa.text("SELECT id FROM prompt_templates WHERE key = :key"), {"key": key}
        ).fetchone()
        if not row:
            continue
        tid = row[0]
        conn.execute(
            sa.text(
                """
                INSERT INTO prompt_versions (
                  prompt_template_id, version, content_md, is_active, created_by, notes
                )
                SELECT :tid, :ver, :content, true, 'seed', 'Initial seed from code prompts'
                WHERE NOT EXISTS (
                  SELECT 1 FROM prompt_versions
                  WHERE prompt_template_id = :tid AND version = :ver
                )
                """
            ),
            {"tid": tid, "ver": version, "content": content},
        )


def downgrade() -> None:
    op.drop_index("ix_content_quality_scores_verdict", table_name="content_quality_scores")
    op.drop_index("ix_content_quality_scores_document_id", table_name="content_quality_scores")
    op.drop_table("content_quality_scores")
    op.drop_index("ix_project_prompt_overrides_project", table_name="project_prompt_overrides")
    op.drop_table("project_prompt_overrides")
    op.drop_index("ix_prompt_versions_template_id", table_name="prompt_versions")
    op.drop_table("prompt_versions")
    op.drop_index("ix_prompt_templates_key", table_name="prompt_templates")
    op.drop_table("prompt_templates")
