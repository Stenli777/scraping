from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentClusterLink(Base):
    __tablename__ = "document_cluster_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id", ondelete="CASCADE"), index=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("topic_clusters.id", ondelete="CASCADE"), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    cluster = relationship("TopicCluster", back_populates="document_links")
