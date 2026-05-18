"""Async LLM enrichment job queue."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnrichmentJobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"

    ACTIVE = frozenset({QUEUED, RUNNING})


class EnrichmentType:
    TOPIC_CLEANUP = "topic_cleanup"
    SEO_CLEANUP = "seo_cleanup"
    QUALITY_RECHECK = "quality_recheck"
    CLUSTER_SUGGESTION = "cluster_suggestion"
    SIMILARITY_ANALYSIS = "similarity_analysis"


class LlmEnrichmentJob(Base):
    __tablename__ = "llm_enrichment_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    enrichment_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default=EnrichmentJobStatus.QUEUED)
    requested_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_alias: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_run_id: Mapped[int | None] = mapped_column(ForeignKey("llm_runs.id", ondelete="SET NULL"), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    parent_enrichment_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("llm_enrichment_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    root_enrichment_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("llm_enrichment_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
