from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    parser_type: Mapped[str] = mapped_column(String(64), default="generic_article")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tasks: Mapped[list["ScrapingTask"]] = relationship(back_populates="source")

    @staticmethod
    def domain_from_url(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc.lower().removeprefix("www.")
