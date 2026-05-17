from typing import Any

from pydantic import BaseModel, Field, model_validator


class LLMRequestBase(BaseModel):
    task_id: int | None = None
    project_id: int | None = None
    content: str
    model_alias: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMResponseBase(BaseModel):
    success: bool = False
    status: str = "error"
    content: str = ""
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RewriteRequest(BaseModel):
    task_id: int | None = None
    project_id: int | None = None
    source_url: str | None = None
    title: str | None = None
    content: str
    model_alias: str
    language: str = "ru"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RewriteResponse(BaseModel):
    success: bool = False
    status: str = "error"
    rewritten_title: str = ""
    rewritten_content: str = ""
    rewritten_text: str = ""
    model_alias: str = ""
    upstream_model: str = ""
    fallback_used: bool = False
    quality_score: float | None = None
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_text_fields(self) -> "RewriteResponse":
        if self.rewritten_content and not self.rewritten_text:
            self.rewritten_text = self.rewritten_content
        elif self.rewritten_text and not self.rewritten_content:
            self.rewritten_content = self.rewritten_text
        return self


class ReviewRequest(BaseModel):
    task_id: int | None = None
    project_id: int | None = None
    document_id: int | None = None
    source_url: str | None = None
    title: str | None = None
    content: str
    model_alias: str
    project_slug: str | None = None
    profile_context: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewResponse(BaseModel):
    success: bool = False
    status: str = "error"
    take: bool = False
    score: int = 0
    reason: str = ""
    target_project: str | None = None
    recommended_angle: str | None = None
    content_type: str | None = None
    risks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    model_alias: str = ""
    upstream_model: str = ""
    fallback_used: bool = False
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SeoEnrichRequest(BaseModel):
    task_id: int | None = None
    project_id: int | None = None
    document_id: int | None = None
    source_url: str | None = None
    title: str | None = None
    content: str
    model_alias: str
    profile_context: str | None = None
    target_keywords: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SeoEnrichResponse(BaseModel):
    success: bool = False
    status: str = "error"
    seo_title: str = ""
    seo_description: str = ""
    h1: str = ""
    slug: str = ""
    excerpt: str = ""
    tags: list[str] = Field(default_factory=list)
    faq: list[dict[str, str]] = Field(default_factory=list)
    suggested_category: str = ""
    model_alias: str = ""
    upstream_model: str = ""
    fallback_used: bool = False
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def seo_metadata(self) -> dict[str, Any]:
        return {
            "seo_title": self.seo_title,
            "seo_description": self.seo_description,
            "h1": self.h1,
            "slug": self.slug,
            "excerpt": self.excerpt,
            "tags": self.tags,
            "faq": self.faq,
            "suggested_category": self.suggested_category,
        }
