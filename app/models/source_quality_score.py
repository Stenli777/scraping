"""Deterministic source quality scoring for discovered URLs."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceQualityScore(Base):
    __tablename__ = "source_quality_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_directory_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_directories.id", ondelete="SET NULL"), nullable=True
    )
    discovered_url_id: Mapped[int | None] = mapped_column(
        ForeignKey("discovered_urls.id", ondelete="CASCADE"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(String(2048))
    domain: Mapped[str] = mapped_column(String(255), index=True)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    relevance_score: Mapped[int] = mapped_column(Integer, default=0)
    trust_score: Mapped[int] = mapped_column(Integer, default=50)
    spam_score: Mapped[int] = mapped_column(Integer, default=0)
    thin_content_score: Mapped[int] = mapped_column(Integer, default=0)
    ai_noise_score: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_risk_score: Mapped[int] = mapped_column(Integer, default=0)
    language_detected: Mapped[str | None] = mapped_column(String(16), nullable=True)
    strategy_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    strategy_block_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scoring_version: Mapped[str] = mapped_column(String(32), default="source_quality_v1")
    scoring_details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
