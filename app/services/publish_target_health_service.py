"""Publish target connectivity and configuration health."""

import os
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.publish_target import PublishTarget
from app.publishers.versions import SUPPORTED_PAYLOAD_FORMATS, is_supported_payload_format
from app.services.publish_service import resolve_target_endpoint


def check_publish_target_health(db: Session, target: PublishTarget) -> dict[str, Any]:
    settings = get_settings()
    endpoint, force_dry = resolve_target_endpoint(target)

    auth_configured = True
    auth_detail = "none"
    if target.auth_type and target.auth_type != "none":
        env_name = target.auth_token_env_name or ""
        token = os.environ.get(env_name, "").strip() if env_name else ""
        auth_configured = bool(token)
        auth_detail = env_name or "missing env name"

    payload_format = target.payload_format or "article_v1"
    payload_supported = is_supported_payload_format(payload_format)

    reachable = False
    reach_detail = "skipped"
    http_status: int | None = None

    if force_dry or target.target_type == "mock":
        reachable = True
        reach_detail = "dry_run_or_mock"
    elif endpoint:
        try:
            with httpx.Client(timeout=min(settings.publish_default_timeout, 10)) as client:
                if endpoint.endswith("/articles/import"):
                    probe_url = endpoint.rsplit("/articles/import", 1)[0] + "/articles"
                else:
                    probe_url = endpoint
                resp = client.get(probe_url)
            http_status = resp.status_code
            reachable = resp.status_code < 500
            reach_detail = f"GET {probe_url} -> {resp.status_code}"
        except Exception as exc:
            reach_detail = str(exc)[:200]

    healthy = (
        target.enabled
        and payload_supported
        and auth_configured
        and (reachable or force_dry)
    )

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
        "healthy": all(c["healthy"] for c in checks) if checks else True,
        "targets": checks,
    }
