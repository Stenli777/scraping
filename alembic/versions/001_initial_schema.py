"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("parser_type", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_sources_source_url", "sources", ["source_url"], unique=True)
    op.create_index("ix_sources_domain", "sources", ["domain"])

    op.create_table(
        "scraping_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("parser_type", sa.String(64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_scraping_tasks_source_url", "scraping_tasks", ["source_url"])
    op.create_index("ix_scraping_tasks_status", "scraping_tasks", ["status"])

    op.create_table(
        "parsed_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("scraping_tasks.id"), unique=True),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=True),
        sa.Column("rewritten_text", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_parsed_documents_source_url", "parsed_documents", ["source_url"])
    op.create_index("ix_parsed_documents_content_hash", "parsed_documents", ["content_hash"])

    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id")),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=True),
        sa.Column("rewritten_text", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])

    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("scraping_tasks.id")),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_task_logs_task_id", "task_logs", ["task_id"])

    op.create_table(
        "exports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("parsed_documents.id")),
        sa.Column("export_type", sa.String(32), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_exports_document_id", "exports", ["document_id"])


def downgrade() -> None:
    op.drop_table("exports")
    op.drop_table("task_logs")
    op.drop_table("document_versions")
    op.drop_table("parsed_documents")
    op.drop_table("scraping_tasks")
    op.drop_table("sources")
