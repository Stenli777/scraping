from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RewriteLineage(Base):
    __tablename__ = "rewrite_lineages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    root_source_document_id: Mapped[int] = mapped_column(
        ForeignKey("parsed_documents.id", ondelete="CASCADE"), index=True
    )
    derived_document_id: Mapped[int] = mapped_column(
        ForeignKey("parsed_documents.id", ondelete="CASCADE"), index=True
    )
    rewrite_generation: Mapped[int] = mapped_column(Integer, default=1)
    lineage_type: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
