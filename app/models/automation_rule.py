from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), default="manual")
    schedule_cron: Mapped[str | None] = mapped_column(String(64), nullable=True)
    automation_type: Mapped[str] = mapped_column(String(64))
    config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=10)
    max_daily_runs: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    runs = relationship("AutomationRun", back_populates="rule")
