from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DraftReviewFeedback(Base):
    __tablename__ = "draft_review_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id", ondelete="CASCADE"), index=True)
    release_candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_release_candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    publish_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("publish_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    publication_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("publication_records.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_changes_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    checked_public_visibility: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_seo: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_content: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_media: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility_check_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
