"""Bounded operational state snapshots (Phase D) ??? not metrics platform."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperationalSnapshot(Base):
    __tablename__ = "operational_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    source: Mapped[str] = mapped_column(String(32), default="diagnostics")
    metrics_json: Mapped[dict] = mapped_column(JSONB)
