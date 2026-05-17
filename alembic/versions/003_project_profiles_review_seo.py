"""Project profiles, review_results, seo_metadata + crmflow24 seed

Revision ID: 003
Revises: 002
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CRMFLOW24_ALLOWED = [
    "Bitrix24",
    "CRM",
    "автоматизация продаж",
    "телефония",
    "интеграции",
    "воронки",
    "кейсы внедрения",
    "CRM migration",
    "отдел продаж",
    "аналитика",
]
CRMFLOW24_BLOCKED = [
    "крипта",
    "политика",
    "мотивация",
    "generic news",
    "unrelated dev articles",
]


def upgrade() -> None:
    op.add_column("projects", sa.Column("content_rules_md", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("rewrite_instructions_md", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("seo_instructions_md", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("review_instructions_md", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("tone_of_voice", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("target_audience", sa.Text(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("allowed_topics_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("blocked_topics_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("default_language", sa.String(16), server_default="ru", nullable=False),
    )

    op.create_table(
        "review_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("scraping_tasks.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id"), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("take", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(64), nullable=True),
        sa.Column("recommended_angle", sa.Text(), nullable=True),
        sa.Column("target_project", sa.String(64), nullable=True),
        sa.Column("risks_json", postgresql.JSONB(), nullable=True),
        sa.Column("warnings_json", postgresql.JSONB(), nullable=True),
        sa.Column("llm_run_id", sa.Integer(), sa.ForeignKey("llm_runs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_review_results_task_id", "review_results", ["task_id"])
    op.create_index("ix_review_results_document_id", "review_results", ["document_id"])
    op.create_index("ix_review_results_project_id", "review_results", ["project_id"])

    op.create_table(
        "seo_metadata",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("scraping_tasks.id"), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("seo_title", sa.String(512), nullable=True),
        sa.Column("seo_description", sa.Text(), nullable=True),
        sa.Column("h1", sa.String(512), nullable=True),
        sa.Column("slug", sa.String(256), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("tags_json", postgresql.JSONB(), nullable=True),
        sa.Column("faq_json", postgresql.JSONB(), nullable=True),
        sa.Column("suggested_category", sa.String(128), nullable=True),
        sa.Column("llm_run_id", sa.Integer(), sa.ForeignKey("llm_runs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_seo_metadata_document_id", "seo_metadata", ["document_id"])

    # Seed / update crmflow24 profile
    import json

    conn = op.get_bind()
    rewrite_md = """## Цель рерайта
- НЕ делать синонимайзинг.
- Писать новую полезную статью на основе фактов источника.
- Добавлять практические рекомендации для бизнеса.
- Формат: Markdown (H1, H2/H3).
- Без воды, для собственника и руководителя отдела продаж."""

    review_md = """Оцени, подходит ли материал для публикации на CRMFlow24.
Учитывай allowed/blocked topics, tone и аудиторию.
Верни структурированный JSON."""

    seo_md = """Сгенерируй SEO-метаданные для статьи CRM/Bitrix24 тематики.
Без keyword stuffing. Читабельно, business-oriented, human-friendly."""

    content_rules = """- Только темы CRM, Bitrix24, продажи, автоматизация.
- Отклонять крипту, политику, мотивацию, generic news и нерелевантный dev-контент."""

    tone = "практичный, business-oriented, без воды, экспертный, понятный собственнику бизнеса"
    audience = "собственники бизнеса, руководители отдела продаж, CRM-администраторы"

    allowed_json = json.dumps(CRMFLOW24_ALLOWED, ensure_ascii=False)
    blocked_json = json.dumps(CRMFLOW24_BLOCKED, ensure_ascii=False)

    existing = conn.execute(
        sa.text("SELECT id FROM projects WHERE slug = 'crmflow24'")
    ).fetchone()

    if existing:
        conn.execute(
            sa.text(
                """
                UPDATE projects SET
                  name = 'CRMFlow24',
                  domain = 'crmflow24.ru',
                  enabled = true,
                  content_rules_md = :content_rules,
                  rewrite_instructions_md = :rewrite_md,
                  seo_instructions_md = :seo_md,
                  review_instructions_md = :review_md,
                  tone_of_voice = :tone,
                  target_audience = :audience,
                  allowed_topics_json = CAST(:allowed AS jsonb),
                  blocked_topics_json = CAST(:blocked AS jsonb),
                  default_language = 'ru',
                  updated_at = now()
                WHERE slug = 'crmflow24'
                """
            ),
            {
                "content_rules": content_rules,
                "rewrite_md": rewrite_md,
                "seo_md": seo_md,
                "review_md": review_md,
                "tone": tone,
                "audience": audience,
                "allowed": allowed_json,
                "blocked": blocked_json,
            },
        )
    else:
        conn.execute(
            sa.text(
                """
                INSERT INTO projects (
                  slug, name, domain, enabled, rewrite_profile, seo_profile, publish_mode,
                  content_rules_md, rewrite_instructions_md, seo_instructions_md,
                  review_instructions_md, tone_of_voice, target_audience,
                  allowed_topics_json, blocked_topics_json, default_language
                ) VALUES (
                  'crmflow24', 'CRMFlow24', 'crmflow24.ru', true, 'default', 'default', 'draft',
                  :content_rules, :rewrite_md, :seo_md, :review_md, :tone, :audience,
                  CAST(:allowed AS jsonb), CAST(:blocked AS jsonb), 'ru'
                )
                """
            ),
            {
                "content_rules": content_rules,
                "rewrite_md": rewrite_md,
                "seo_md": seo_md,
                "review_md": review_md,
                "tone": tone,
                "audience": audience,
                "allowed": allowed_json,
                "blocked": blocked_json,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_seo_metadata_document_id", table_name="seo_metadata")
    op.drop_table("seo_metadata")
    op.drop_index("ix_review_results_project_id", table_name="review_results")
    op.drop_index("ix_review_results_document_id", table_name="review_results")
    op.drop_index("ix_review_results_task_id", table_name="review_results")
    op.drop_table("review_results")
    op.drop_column("projects", "default_language")
    op.drop_column("projects", "blocked_topics_json")
    op.drop_column("projects", "allowed_topics_json")
    op.drop_column("projects", "target_audience")
    op.drop_column("projects", "tone_of_voice")
    op.drop_column("projects", "review_instructions_md")
    op.drop_column("projects", "seo_instructions_md")
    op.drop_column("projects", "rewrite_instructions_md")
    op.drop_column("projects", "content_rules_md")
