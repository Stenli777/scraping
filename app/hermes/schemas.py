"""Pydantic schemas for Hermes HTTP orchestration contract."""

from typing import Any

from pydantic import BaseModel, Field


class HermesTaskRequest(BaseModel):
    task_kind: str
    agent: str = "hermes-smart"
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HermesTaskResponse(BaseModel):
    success: bool = False
    result: dict[str, Any] | str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    agent_used: str | None = None
    model_used: str | None = None
    fallback_used: bool = False
    raw: dict[str, Any] | None = None


class HermesAgentInfo(BaseModel):
    alias: str
    description: str
    upstream_hint: str | None = None


class HermesHealthResponse(BaseModel):
    available: bool
    status: str = "unknown"
    latency_ms: int = 0
    service: str | None = None
    version: str | None = None
    detail: str | None = None
    raw: dict[str, Any] | None = None
