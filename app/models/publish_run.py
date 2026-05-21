from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PublishRun(Base):
    __tablename__ = "publish_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("scraping_tasks.id"), nullable=True)
    publish_target_id: Mapped[int] = mapped_column(ForeignKey("publish_targets.id"), index=True)
    document_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    preview_media_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32))
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    endpoint_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    request_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    draft_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    payload_version: Mapped[str] = mapped_column(String(32), default="article_v1")
    force_used: Mapped[bool] = mapped_column(Boolean, default=False)
    force_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_parent_publish_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("publish_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    release_candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_release_candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_retry_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_schema_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    remote_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document_revision = relationship("DocumentRevision", back_populates="publish_runs")
