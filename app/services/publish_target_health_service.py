"""Publish target connectivity and configuration health."""

import os
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_crmflow24_publish_endpoint, get_crmflow24_publish_token_env_names, get_settings
from app.models.publish_target import PublishTarget
from app.publishers.versions import SUPPORTED_PAYLOAD_FORMATS, is_supported_payload_format
from app.services.publish_service import resolve_target_endpoint


def _resolve_token(target: PublishTarget) -> tuple[bool, str]:
    if not target.auth_type or target.auth_type == "none":
        return True, "none"
    env_name = target.auth_token_env_name or ""
    names = [env_name] if env_name else []
    for alt in get_crmflow24_publish_token_env_names():
        if alt not in names:
            names.append(alt)
    for name in names:
        if name and os.environ.get(name, "").strip():
            return True, name
    return False, env_name or "missing"


def _safe_probe(endpoint: str, headers: dict[str, str], timeout: int) -> tuple[bool, str, int | None]:
    """Probe without creating content; 401/403/404/405 still count as reachable."""
    try:
        with httpx.Client(timeout=timeout) as client:
            for method in ("OPTIONS", "HEAD", "GET"):
                try:
                    resp = client.request(method, endpoint, headers=headers)
                    status = resp.status_code
                    ok = status < 500
                    return ok, f"{method} {endpoint} -> {status}", status
                except httpx.HTTPError:
                    continue
    except Exception as exc:
        return False, str(exc)[:200], None
    return False, "probe failed", None


def check_publish_target_health(db: Session, target: PublishTarget) -> dict[str, Any]:
    settings = get_settings()
    endpoint, force_dry = resolve_target_endpoint(target)

    auth_configured, auth_detail = _resolve_token(target)

    payload_format = target.payload_format or "article_v1"
    payload_supported = is_supported_payload_format(payload_format)

    reachable = False
    reach_detail = "skipped"
    http_status: int | None = None

    if force_dry or target.target_type == "mock":
        reachable = True
        reach_detail = "dry_run_or_mock"
    elif endpoint:
        headers: dict[str, str] = {}
        if auth_configured and target.auth_type == "bearer":
            for name in ([target.auth_token_env_name] if target.auth_token_env_name else []) + list(
                get_crmflow24_publish_token_env_names()
            ):
                tok = os.environ.get(name or "", "").strip()
                if tok:
                    headers["Authorization"] = f"Bearer {tok}"
                    break
        parsed = urlparse(endpoint)
        is_external = parsed.hostname and "crmflow24.ru" in (parsed.hostname or "")
        if is_external:
            reachable, reach_detail, http_status = _safe_probe(
                endpoint, headers, min(settings.publish_default_timeout, 10)
            )
            if http_status in (401, 403) and not headers.get("Authorization"):
                reach_detail += " (auth header missing)"
        else:
            probe_url = endpoint
            if endpoint.endswith("/articles/import"):
                probe_url = endpoint.rsplit("/articles/import", 1)[0] + "/articles"
            reachable, reach_detail, http_status = _safe_probe(
                probe_url, headers, min(settings.publish_default_timeout, 10)
            )

    healthy = target.enabled and payload_supported and auth_configured and (reachable or force_dry)

    return {
        "target_id": target.id,
        "name": target.name,
        "healthy": healthy,
        "enabled": target.enabled,
        "target_type": target.target_type,
        "endpoint": endpoint or None,
        "dry_run": target.dry_run or force_dry,
        "payload_format": payload_format,
        "payload_supported": payload_supported,
        "supported_payload_formats": sorted(SUPPORTED_PAYLOAD_FORMATS),
        "auth_configured": auth_configured,
        "auth_detail": auth_detail,
        "reachable": reachable,
        "reach_detail": reach_detail,
        "http_status": http_status,
    }


def check_all_publish_targets_health(db: Session) -> dict[str, Any]:
    targets = db.query(PublishTarget).order_by(PublishTarget.id.asc()).all()
    checks = [check_publish_target_health(db, t) for t in targets]
    return {
        "healthy": all(c["healthy"] for c in checks if c["name"] != "crmflow24-webhook-test") if checks else True,
        "targets": checks,
    }
