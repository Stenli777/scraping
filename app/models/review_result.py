from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewResult(Base):
    __tablename__ = "review_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("scraping_tasks.id"), nullable=True, index=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("parsed_documents.id"), nullable=True, index=True
    )
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    take: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommended_angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_project: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risks_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    warnings_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    llm_run_id: Mapped[int | None] = mapped_column(ForeignKey("llm_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
