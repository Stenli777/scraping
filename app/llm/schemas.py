from typing import Any

from pydantic import BaseModel, Field


class LLMRequestBase(BaseModel):
    task_id: int | None = None
    project_id: int | None = None
    content: str
    model_alias: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMResponseBase(BaseModel):
    status: str = "ok"
    content: str = ""
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RewriteRequest(LLMRequestBase):
    pass


class RewriteResponse(LLMResponseBase):
    rewritten_text: str = ""


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
