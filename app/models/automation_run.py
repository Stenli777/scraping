from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AutomationRun(Base):
    __tablename__ = "automation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    automation_rule_id: Mapped[int] = mapped_column(
        ForeignKey("automation_rules.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    affected_entities_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    logs_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_tasks: Mapped[int] = mapped_column(Integer, default=0)
    created_documents: Mapped[int] = mapped_column(Integer, default=0)
    created_discoveries: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rule = relationship("AutomationRule", back_populates="runs")
