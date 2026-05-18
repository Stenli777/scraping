from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CanonicalContentGroup(Base):
    __tablename__ = "canonical_content_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    canonical_slug: Mapped[str] = mapped_column(String(512))
    canonical_title: Mapped[str] = mapped_column(String(1024), default="")
    primary_topic: Mapped[str | None] = mapped_column(String(512), nullable=True)
    strategy_status: Mapped[str] = mapped_column(String(32), default="open")
    duplicate_risk_level: Mapped[str] = mapped_column(String(32), default="low")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    documents: Mapped[list["ParsedDocument"]] = relationship(back_populates="canonical_group")
