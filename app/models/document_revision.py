from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.parsed_document import ParsedDocument
    from app.models.publish_run import PublishRun


class DocumentRevision(Base):
    __tablename__ = "document_revisions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "revision_number",
            name="uq_document_revisions_document_revision",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id", ondelete="CASCADE"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(32))
    source_reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rewrite_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quality_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    editorial_status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["ParsedDocument"] = relationship(back_populates="revisions")
    publish_runs: Mapped[list["PublishRun"]] = relationship(back_populates="document_revision")
