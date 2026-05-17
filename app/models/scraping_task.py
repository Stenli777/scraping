from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TaskStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.parsed_document import ParsedDocument
    from app.models.source import Source
    from app.models.task_log import TaskLog


class ScrapingTask(Base):
    __tablename__ = "scraping_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    source_url: Mapped[str] = mapped_column(String(2048), index=True)
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.QUEUED, index=True)
    parser_type: Mapped[str] = mapped_column(String(64), default="generic_article")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source: Mapped["Source | None"] = relationship(back_populates="tasks")
    document: Mapped["ParsedDocument | None"] = relationship(
        back_populates="task", uselist=False
    )
    logs: Mapped[list["TaskLog"]] = relationship(back_populates="task", cascade="all, delete-orphan")
