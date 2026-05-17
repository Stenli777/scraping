"""HTTP-only Hermes connector with retries, audit, and safe fallback."""

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.feature_flags import (
    is_hermes_campaigns_enabled,
    is_hermes_enabled,
    is_hermes_reasoning_enabled,
)
from app.hermes.adapters import cliproxy_system_prompt
from app.hermes.exceptions import (
    HermesDisabledError,
    HermesResponseError,
    HermesTimeoutError,
    HermesUnavailableError,
)
from app.hermes.routing import resolve_hermes_agent
from app.hermes.schemas import HermesTaskRequest, HermesTaskResponse

logger = logging.getLogger(__name__)

ORCHESTRATE_PATH = "/v1/orchestrate"


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    out = dict(headers)
    if "Authorization" in out:
        out["Authorization"] = "Bearer ***"
    return out


def _orchestrate_url() -> str:
    settings = get_settings()
    if settings.hermes_orchestrate_url:
        return settings.hermes_orchestrate_url.rstrip("/")
    base = (settings.hermes_base_url or "http://127.0.0.1:8000").rstrip("/")
    return f"{base}{ORCHESTRATE_PATH}"


def _task_flag_ok(task_kind: str) -> bool:
    from app.core.feature_flags import is_hermes_research_enabled

    if task_kind == "research_summary":
        return is_hermes_research_enabled()
    if task_kind == "rewrite_critique":
        return is_hermes_reasoning_enabled()
    if task_kind == "campaign_ideas":
        return is_hermes_campaigns_enabled()
    return is_hermes_reasoning_enabled()


class HermesClient:
    def run_task(self, request: HermesTaskRequest) -> HermesTaskResponse:
        if not is_hermes_enabled():
            raise HermesDisabledError("Hermes integration disabled (ENABLE_HERMES=false)")
        if not _task_flag_ok(request.task_kind):
            raise HermesDisabledError(
                f"Hermes task {request.task_kind} disabled by feature flags"
            )

        route = resolve_hermes_agent(request.agent)
        settings = get_settings()
        timeout = request.timeout or settings.hermes_timeout
        url = _orchestrate_url()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.hermes_api_key:
            headers["Authorization"] = f"Bearer {settings.hermes_api_key}"

        body = {
            "task_kind": request.task_kind,
            "agent": route.orchestrate_agent,
            "payload": request.payload,
            "metadata": request.metadata,
        }

        last_error: str | None = None
        for attempt in range(max(1, settings.hermes_max_retries + 1)):
            started = time.perf_counter()
            try:
                with httpx.Client(timeout=float(timeout)) as client:
                    resp = client.post(url, json=body, headers=headers)
                latency_ms = int((time.perf_counter() - started) * 1000)

                if resp.status_code == 404:
                    logger.info(
                        "Hermes orchestrate endpoint not found (%s), using cliproxy fallback",
                        url,
                    )
                    return self._cliproxy_fallback(
                        request, route=route, latency_ms=latency_ms, reason="orchestrate_404"
                    )

                if resp.status_code >= 500:
                    last_error = f"HTTP {resp.status_code}"
                    continue

                if resp.status_code >= 400:
                    raise HermesResponseError(f"Hermes HTTP {resp.status_code}: {resp.text[:500]}")

                data = resp.json()
                return HermesTaskResponse(
                    success=bool(data.get("success", True)),
                    result=data.get("result", data),
                    warnings=[str(w) for w in (data.get("warnings") or [])],
                    errors=[str(e) for e in (data.get("errors") or [])],
                    latency_ms=latency_ms,
                    agent_used=data.get("agent_used") or route.alias,
                    model_used=data.get("model_used"),
                    fallback_used=False,
                    raw=data if isinstance(data, dict) else None,
                )

            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
                logger.warning("Hermes orchestrate timeout attempt=%s", attempt + 1)
            except httpx.ConnectError as exc:
                last_error = f"connect: {exc}"
                logger.warning("Hermes orchestrate connect error: %s", exc)
                break
            except HermesResponseError:
                raise
            except json.JSONDecodeError as exc:
                raise HermesResponseError(f"Invalid JSON from Hermes: {exc}") from exc
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Hermes orchestrate error: %s", exc)

        if last_error and "connect" in last_error:
            if settings.hermes_allow_cliproxy_fallback:
                return self._cliproxy_fallback(
                    request,
                    route=route,
                    latency_ms=0,
                    reason=last_error,
                )
            raise HermesUnavailableError(last_error)

        if settings.hermes_allow_cliproxy_fallback and last_error:
            return self._cliproxy_fallback(
                request, route=route, latency_ms=0, reason=last_error or "unknown"
            )

        if "timeout" in (last_error or ""):
            raise HermesTimeoutError(last_error or "timeout")
        raise HermesUnavailableError(last_error or "Hermes request failed")

    def _cliproxy_fallback(
        self,
        request: HermesTaskRequest,
        *,
        route,
        latency_ms: int,
        reason: str,
    ) -> HermesTaskResponse:
        """Reasoning via CLIProxy when Hermes orchestrate API is not deployed — audit as fallback."""
        from app.llm.client import LLMClient
        from app.llm.json_utils import parse_llm_json

        settings = get_settings()
        model_alias = route.cliproxy_model_alias or settings.rewrite_model_alias
        user_content = json.dumps(request.payload, ensure_ascii=False)
        messages = [
            {"role": "system", "content": cliproxy_system_prompt(request.task_kind)},
            {"role": "user", "content": user_content},
        ]

        started = time.perf_counter()
        client = LLMClient()
        try:
            result = client.complete(model_alias=model_alias, messages=messages)
            elapsed = int((time.perf_counter() - started) * 1000)
            try:
                parsed = parse_llm_json(result.content)
                result_data: Any = parsed
            except ValueError:
                result_data = {"text": result.content}

            return HermesTaskResponse(
                success=True,
                result=result_data,
                warnings=[f"cliproxy_fallback: {reason}"],
                errors=[],
                latency_ms=latency_ms or elapsed,
                agent_used=route.alias,
                model_used=result.upstream_model or model_alias,
                fallback_used=True,
                raw={"fallback_reason": reason},
            )
        except Exception as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.warning("Hermes cliproxy fallback failed: %s", exc)
            return HermesTaskResponse(
                success=False,
                result=None,
                warnings=[f"cliproxy_fallback attempted: {reason}"],
                errors=[str(exc)],
                latency_ms=latency_ms or elapsed,
                agent_used=route.alias,
                model_used=model_alias,
                fallback_used=True,
            )
