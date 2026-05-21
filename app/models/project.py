from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rewrite_profile: Mapped[str] = mapped_column(String(64), default="default")
    seo_profile: Mapped[str] = mapped_column(String(64), default="default")
    publish_mode: Mapped[str] = mapped_column(String(32), default="draft")
    minimum_review_score_for_publish: Mapped[int] = mapped_column(Integer, default=60)
    require_review_take_for_publish: Mapped[bool] = mapped_column(Boolean, default=True)
    trust_level: Mapped[int] = mapped_column(Integer, default=0)

    content_rules_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewrite_instructions_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_instructions_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_instructions_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_of_voice: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_topics_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    blocked_topics_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    default_language: Mapped[str] = mapped_column(String(16), default="ru")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source_directories: Mapped[list["SourceDirectory"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    publish_targets: Mapped[list["PublishTarget"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
