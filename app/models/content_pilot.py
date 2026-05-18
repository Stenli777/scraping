from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

PILOT_STATUSES = frozenset({"draft", "active", "completed", "archived"})
PILOT_ITEM_STATUSES = frozenset({
    "candidate",
    "in_progress",
    "draft_created",
    "draft_reviewed",
    "public_confirmed",
    "analytics_started",
    "blocked",
    "done",
})


class ContentPilot(Base):
    __tablename__ = "content_pilots"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_content_pilots_project_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    target_count: Mapped[int] = mapped_column(Integer, default=5)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items = relationship("ContentPilotItem", back_populates="pilot", cascade="all, delete-orphan")


class ContentPilotItem(Base):
    __tablename__ = "content_pilot_items"
    __table_args__ = (UniqueConstraint("pilot_id", "document_id", name="uq_content_pilot_items_pilot_document"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pilot_id: Mapped[int] = mapped_column(ForeignKey("content_pilots.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id", ondelete="CASCADE"), index=True)
    release_candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_release_candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    publication_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("publication_records.id", ondelete="SET NULL"), nullable=True, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(32), default="candidate", index=True)
    next_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    blockers_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pilot = relationship("ContentPilot", back_populates="items")
    document = relationship("ParsedDocument")
    release_candidate = relationship("ContentReleaseCandidate")
    publication_record = relationship("PublicationRecord")
