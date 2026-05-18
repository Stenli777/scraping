from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CLUSTER_TYPES = frozenset(
    {"commercial", "informational", "comparison", "integration", "guide", "case_study"}
)


class TopicCluster(Base):
    __tablename__ = "topic_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128), index=True)
    cluster_type: Mapped[str] = mapped_column(String(32), default="informational")
    primary_keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secondary_keywords_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    search_intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document_links = relationship("DocumentClusterLink", back_populates="cluster", cascade="all, delete-orphan")
