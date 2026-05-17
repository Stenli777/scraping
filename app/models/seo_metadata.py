from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SeoMetadata(Base):
    __tablename__ = "seo_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("scraping_tasks.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(String(512), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(256), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    faq_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    suggested_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_run_id: Mapped[int | None] = mapped_column(ForeignKey("llm_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
