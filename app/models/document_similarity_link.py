from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.canonical_content_group import CanonicalContentGroup


class DocumentSimilarityLink(Base):
    __tablename__ = "document_similarity_links"
    __table_args__ = (
        CheckConstraint("document_id_a < document_id_b", name="ck_similarity_link_ordered_ids"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    document_id_a: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id", ondelete="CASCADE"))
    document_id_b: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id", ondelete="CASCADE"))
    canonical_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("canonical_content_groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    similarity_score: Mapped[int] = mapped_column(Integer, default=0)
    similarity_type: Mapped[str] = mapped_column(String(64), index=True)
    title_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    keyword_overlap: Mapped[float] = mapped_column(Float, default=0.0)
    topic_overlap: Mapped[float] = mapped_column(Float, default=0.0)
    rewrite_overlap: Mapped[float] = mapped_column(Float, default=0.0)
    duplicate_risk: Mapped[str] = mapped_column(String(32), default="low")
    strategy_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    canonical_group: Mapped["CanonicalContentGroup | None"] = relationship()
