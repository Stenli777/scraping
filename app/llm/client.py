import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.llm.exceptions import ProviderError
from app.llm.models import CompletionResult
from app.llm.registry import resolve_model_route

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI-compatible client via CLIProxyAPI only."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def _endpoint(self) -> str:
        base = (self.settings.cliproxyapi_base_url or "").rstrip("/")
        if not base:
            raise ProviderError("CLIPROXYAPI_BASE_URL is not configured")
        return f"{base}/v1/chat/completions"

    def _headers(self) -> dict[str, str]:
        key = self.settings.cliproxyapi_api_key
        if not key:
            raise ProviderError("CLIPROXYAPI_API_KEY is not configured")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def complete(
        self,
        *,
        model_alias: str,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        timeout_seconds: int | None = None,
    ) -> CompletionResult:
        route = resolve_model_route(model_alias)
        models_to_try = [route.upstream_model]
        if route.fallback_upstream_model:
            models_to_try.append(route.fallback_upstream_model)

        last_error: Exception | None = None
        for idx, upstream_model in enumerate(models_to_try):
            fallback_used = idx > 0
            try:
                return self._call(
                    upstream_model=upstream_model,
                    messages=messages,
                    temperature=temperature,
                    alias=route.alias,
                    fallback_used=fallback_used,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM call failed alias=%s model=%s: %s",
                    route.alias,
                    upstream_model,
                    exc,
                )
        raise ProviderError(str(last_error) if last_error else "LLM call failed")

    def _call(
        self,
        *,
        upstream_model: str,
        messages: list[dict[str, str]],
        temperature: float,
        alias: str,
        fallback_used: bool,
        timeout_seconds: int | None = None,
    ) -> CompletionResult:
        payload: dict[str, Any] = {
            "model": upstream_model,
            "messages": messages,
            "temperature": temperature,
        }
        timeout = timeout_seconds if timeout_seconds is not None else self.settings.cliproxyapi_default_timeout
        max_retries = self.settings.cliproxyapi_max_retries
        started = time.perf_counter()

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        self._endpoint(),
                        json=payload,
                        headers=self._headers(),
                    )
                    response.raise_for_status()
                    data = response.json()
                break
            except httpx.HTTPError as exc:
                if attempt >= max_retries:
                    raise ProviderError(f"CLIProxyAPI HTTP error: {exc}") from exc
                logger.info("Retry LLM attempt %s alias=%s", attempt + 1, alias)

        latency_ms = int((time.perf_counter() - started) * 1000)
        choice = data["choices"][0]
        usage = data.get("usage") or {}
        return CompletionResult(
            content=choice["message"]["content"],
            upstream_model=upstream_model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason"),
            fallback_used=fallback_used,
        )
