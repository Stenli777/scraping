"""Source discovery: extend source_directories, discovered_urls, seeds

Revision ID: 005
Revises: 004
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename url -> base_url, last_crawled_at -> last_discovered_at
    op.alter_column("source_directories", "url", new_column_name="base_url")
    op.alter_column("source_directories", "last_crawled_at", new_column_name="last_discovered_at")

    op.add_column("source_directories", sa.Column("name", sa.String(255), nullable=True))
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE source_directories SET name = 'legacy-' || id::text WHERE name IS NULL"))
    op.alter_column("source_directories", "name", nullable=False)
    op.add_column(
        "source_directories",
        sa.Column("discovery_mode", sa.String(32), server_default="mixed"),
    )
    op.add_column(
        "source_directories",
        sa.Column("max_urls_per_run", sa.Integer(), server_default="50"),
    )
    op.add_column(
        "source_directories",
        sa.Column("max_depth", sa.Integer(), server_default="1"),
    )
    op.add_column(
        "source_directories",
        sa.Column("crawl_delay_seconds", sa.Integer(), server_default="1"),
    )
    op.add_column(
        "source_directories",
        sa.Column("allow_patterns_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "source_directories",
        sa.Column("block_patterns_json", postgresql.JSONB(), nullable=True),
    )

    op.drop_column("source_directories", "directory_type")
    op.drop_column("source_directories", "config_json")

    op.create_table(
        "discovered_urls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "source_directory_id",
            sa.Integer(),
            sa.ForeignKey("source_directories.id"),
            nullable=False,
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("normalized_url", sa.String(2048), nullable=False),
        sa.Column("canonical_url", sa.String(2048), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("discovery_source", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="discovered"),
        sa.Column("duplicate_of_id", sa.Integer(), sa.ForeignKey("discovered_urls.id"), nullable=True),
        sa.Column("existing_task_id", sa.Integer(), sa.ForeignKey("scraping_tasks.id"), nullable=True),
        sa.Column(
            "existing_document_id",
            sa.Integer(),
            sa.ForeignKey("parsed_documents.id"),
            nullable=True,
        ),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_discovered_urls_project_id", "discovered_urls", ["project_id"])
    op.create_index(
        "ix_discovered_urls_source_directory_id", "discovered_urls", ["source_directory_id"]
    )
    op.create_index("ix_discovered_urls_status", "discovered_urls", ["status"])
    op.create_index(
        "ix_discovered_urls_normalized_url",
        "discovered_urls",
        ["normalized_url"],
        unique=True,
    )

    row = conn.execute(sa.text("SELECT id FROM projects WHERE slug = 'crmflow24'")).fetchone()
    if row:
        pid = row[0]
        import json

        seeds = [
            {
                "name": "saltpro-blog",
                "base_url": "https://www.saltpro.ru/blog/",
                "discovery_mode": "html_links",
                "allow": ["/blog/", "/articles/"],
                "block": ["/login", "/tag/", "/author/", "/search", "/comments", "/page/"],
            },
            {
                "name": "sotbit-blog",
                "base_url": "https://www.sotbit.ru/blog/",
                "discovery_mode": "html_links",
                "allow": ["/blog/", "/info/"],
                "block": ["/login", "/tag/", "/author/", "/search", "/page/"],
            },
            {
                "name": "habr-articles",
                "base_url": "https://habr.com/ru/articles/",
                "discovery_mode": "html_links",
                "allow": ["/ru/articles/", "/ru/companies/"],
                "block": ["/login", "/search", "/users/", "/comments", "/page"],
            },
        ]
        for s in seeds:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO source_directories (
                      project_id, name, base_url, discovery_mode, enabled,
                      max_urls_per_run, max_depth, crawl_delay_seconds,
                      allow_patterns_json, block_patterns_json
                    )
                    SELECT :pid, :name, :base_url, :mode, true, 20, 1, 1,
                           CAST(:allow AS jsonb), CAST(:block AS jsonb)
                    WHERE NOT EXISTS (
                      SELECT 1 FROM source_directories
                      WHERE project_id = :pid AND name = :name
                    )
                    """
                ),
                {
                    "pid": pid,
                    "name": s["name"],
                    "base_url": s["base_url"],
                    "mode": s["discovery_mode"],
                    "allow": json.dumps(s["allow"], ensure_ascii=False),
                    "block": json.dumps(s["block"], ensure_ascii=False),
                },
            )


def downgrade() -> None:
    op.drop_index("ix_discovered_urls_normalized_url", table_name="discovered_urls")
    op.drop_index("ix_discovered_urls_status", table_name="discovered_urls")
    op.drop_index("ix_discovered_urls_source_directory_id", table_name="discovered_urls")
    op.drop_index("ix_discovered_urls_project_id", table_name="discovered_urls")
    op.drop_table("discovered_urls")

    op.add_column(
        "source_directories",
        sa.Column("config_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "source_directories",
        sa.Column("directory_type", sa.String(32), server_default="sitemap"),
    )
    op.drop_column("source_directories", "block_patterns_json")
    op.drop_column("source_directories", "allow_patterns_json")
    op.drop_column("source_directories", "crawl_delay_seconds")
    op.drop_column("source_directories", "max_depth")
    op.drop_column("source_directories", "max_urls_per_run")
    op.drop_column("source_directories", "discovery_mode")
    op.drop_column("source_directories", "name")
    op.alter_column("source_directories", "last_discovered_at", new_column_name="last_crawled_at")
    op.alter_column("source_directories", "base_url", new_column_name="url")
