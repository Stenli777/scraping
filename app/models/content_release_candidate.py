from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document_revision import DocumentRevision
    from app.models.parsed_document import ParsedDocument
    from app.models.publish_target import PublishTarget


class ContentReleaseCandidate(Base):
    __tablename__ = "content_release_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id", ondelete="CASCADE"), index=True)
    document_revision_id: Mapped[int] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    qa_score: Mapped[int] = mapped_column(Integer, default=0)
    blocking_issues_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    warnings_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    checklist_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    publish_target_id: Mapped[int | None] = mapped_column(
        ForeignKey("publish_targets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload_version: Mapped[str] = mapped_column(String(32), default="article_v2")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    draft_review_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    draft_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped["ParsedDocument"] = relationship()
    document_revision: Mapped["DocumentRevision"] = relationship()
    publish_target: Mapped["PublishTarget | None"] = relationship()
