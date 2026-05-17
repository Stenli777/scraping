from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HermesRun(Base):
    __tablename__ = "hermes_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_kind: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("parsed_documents.id"), nullable=True, index=True
    )
    request_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agent_requested: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
