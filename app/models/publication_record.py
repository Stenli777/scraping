from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PublicationRecord(Base):
    __tablename__ = "publication_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id"), index=True)
    revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    publish_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("publish_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_article_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    publication_status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    draft_review_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    draft_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_operator_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshots = relationship("AnalyticsSnapshot", back_populates="publication_record")
    performance = relationship("ContentPerformance", back_populates="publication_record", uselist=False)
