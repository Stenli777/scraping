from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContentPerformance(Base):
    __tablename__ = "content_performance"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id"), index=True)
    publication_record_id: Mapped[int] = mapped_column(
        ForeignKey("publication_records.id", ondelete="CASCADE"), unique=True
    )
    latest_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_conversions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    performance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trend: Mapped[str | None] = mapped_column(String(16), default="unknown")
    status: Mapped[str | None] = mapped_column(String(16), default="average")
    performance_feedback_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    publication_record = relationship("PublicationRecord", back_populates="performance")
