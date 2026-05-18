from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document_revision import DocumentRevision
    from app.models.document_version import DocumentVersion
    from app.models.export import Export
    from app.models.scraping_task import ScrapingTask


class ParsedDocument(Base):
    __tablename__ = "parsed_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("scraping_tasks.id"), unique=True)
    canonical_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("canonical_content_groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    clean_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewritten_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    editorial_status: Mapped[str] = mapped_column(String(32), default="generated", index=True)
    editorial_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    operator_rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    operator_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_for_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    current_revision_number: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    task: Mapped["ScrapingTask"] = relationship(back_populates="document")
    canonical_group: Mapped["CanonicalContentGroup | None"] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    exports: Mapped[list["Export"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    revisions: Mapped[list["DocumentRevision"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
