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


class ReviewRequest(LLMRequestBase):
    criteria: str | None = None


class ReviewResponse(LLMResponseBase):
    approved: bool = False
    score: float | None = None
    notes: str = ""


class SeoEnrichRequest(LLMRequestBase):
    target_keywords: list[str] = Field(default_factory=list)


class SeoEnrichResponse(LLMResponseBase):
    enriched_text: str = ""
    seo_metadata: dict[str, Any] = Field(default_factory=dict)
