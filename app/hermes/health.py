"""Hermes availability checks — timeout-safe, non-blocking."""

import logging
import time

import httpx

from app.core.config import get_settings
from app.core.feature_flags import is_hermes_enabled
from app.hermes.schemas import HermesHealthResponse

logger = logging.getLogger(__name__)


def _health_url() -> str:
    settings = get_settings()
    base = (settings.hermes_base_url or "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/health"


def check_hermes_health(*, timeout: float | None = None) -> HermesHealthResponse:
    if not is_hermes_enabled():
        return HermesHealthResponse(
            available=False,
            status="disabled",
            detail="ENABLE_HERMES=false",
        )

    settings = get_settings()
    url = _health_url()
    tmo = timeout if timeout is not None else min(float(settings.hermes_timeout), 10.0)
    headers: dict[str, str] = {}
    if settings.hermes_api_key:
        headers["Authorization"] = f"Bearer {settings.hermes_api_key}"

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=tmo) as client:
            resp = client.get(url, headers=headers)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code >= 500:
            return HermesHealthResponse(
                available=False,
                status="error",
                latency_ms=latency_ms,
                detail=f"HTTP {resp.status_code}",
            )
        data = resp.json() if resp.content else {}
        status = str(data.get("status", "ok" if resp.status_code < 400 else "error"))
        available = resp.status_code < 400 and status in ("ok", "degraded")
        return HermesHealthResponse(
            available=available,
            status=status,
            latency_ms=latency_ms,
            service=data.get("service"),
            version=data.get("version"),
            detail=None if available else status,
            raw=data if isinstance(data, dict) else None,
        )
    except httpx.TimeoutException:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.warning("Hermes health timeout url=%s", url)
        return HermesHealthResponse(
            available=False,
            status="timeout",
            latency_ms=latency_ms,
            detail="timeout",
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.warning("Hermes health failed url=%s: %s", url, exc)
        return HermesHealthResponse(
            available=False,
            status="error",
            latency_ms=latency_ms,
            detail=str(exc),
        )
