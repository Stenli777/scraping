from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class SourceDirectory(Base):
    """Controlled discovery entry points for a project."""

    __tablename__ = "source_directories"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str] = mapped_column(String(2048))
    discovery_mode: Mapped[str] = mapped_column(String(32), default="mixed")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_urls_per_run: Mapped[int] = mapped_column(Integer, default=50)
    max_depth: Mapped[int] = mapped_column(Integer, default=1)
    crawl_delay_seconds: Mapped[int] = mapped_column(Integer, default=1)
    allow_patterns_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    block_patterns_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    last_discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="source_directories")
