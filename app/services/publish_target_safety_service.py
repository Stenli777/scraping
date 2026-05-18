"""Publish target classification and safety validation (mock / test / production)."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from app.models.publish_target import PublishTarget

TARGET_CLASS_MOCK = "mock"
TARGET_CLASS_TEST = "test"
TARGET_CLASS_PRODUCTION = "production"

LEVEL_ERROR = "error"
LEVEL_WARN = "warn"


def classify_publish_target(target: PublishTarget) -> str:
    name = (target.name or "").lower()
    endpoint = (target.endpoint_url or "").lower()
    env_name = (target.auth_token_env_name or "").lower()

    if target.target_type == "mock" or "mock" in name or "/api/mock-crmflow24" in endpoint:
        return TARGET_CLASS_MOCK
    if (
        "test" in name
        or "bad-token" in name
        or "placeholder" in env_name
        or env_name.startswith("scrap_bad")
    ):
        return TARGET_CLASS_TEST
    if "crmflow24.ru" in endpoint or "production" in name:
        return TARGET_CLASS_PRODUCTION
    if endpoint.startswith("http://127.0.0.1") or endpoint.startswith("http://localhost"):
        return TARGET_CLASS_MOCK
    return TARGET_CLASS_TEST


def should_ignore_in_default_health(target: PublishTarget) -> bool:
    """Test/disabled targets must not fail aggregate health."""
    if not target.enabled:
        return True
    cls = classify_publish_target(target)
    if cls == TARGET_CLASS_TEST:
        return True
    if target.name in ("crmflow24-webhook-test",):
        return True
    return False


def should_include_in_smoke_health(target: PublishTarget) -> bool:
    cls = classify_publish_target(target)
    if cls == TARGET_CLASS_PRODUCTION:
        return False
    if cls == TARGET_CLASS_TEST:
        return False
    return target.enabled


def validate_publish_target_safety(target: PublishTarget) -> dict[str, Any]:
    """Return safety profile without revealing secrets."""
    issues: list[dict[str, str]] = []
    cls = classify_publish_target(target)
    endpoint = (target.endpoint_url or "").strip()
    parsed = urlparse(endpoint) if endpoint else None
    hostname = (parsed.hostname or "").lower() if parsed else ""

    if cls == TARGET_CLASS_MOCK:
        if target.auth_type == "bearer" and target.auth_token_env_name:
            prod_envs = {"crmflow24_publish_token", "crmflow24_api_token"}
            if target.auth_token_env_name.lower() in prod_envs:
                issues.append(
                    {
                        "level": LEVEL_ERROR,
                        "code": "mock_uses_production_token_env",
                        "message": "Mock target must not use production token env",
                    }
                )
            else:
                issues.append(
                    {
                        "level": LEVEL_WARN,
                        "code": "mock_has_bearer_auth",
                        "message": "Mock target has bearer auth configured (prefer none for local mock)",
                    }
                )
        if hostname and "crmflow24.ru" in hostname:
            issues.append(
                {
                    "level": LEVEL_ERROR,
                    "code": "mock_external_domain",
                    "message": "Mock target must not point to crmflow24.ru",
                }
            )
        if not target.dry_run and endpoint and "/mock-crmflow24" not in endpoint:
            issues.append(
                {
                    "level": LEVEL_WARN,
                    "code": "mock_dry_run_off",
                    "message": "Mock target has dry_run=false",
                }
            )

    if cls == TARGET_CLASS_PRODUCTION:
        if not target.auth_token_env_name:
            issues.append(
                {
                    "level": LEVEL_ERROR,
                    "code": "production_missing_token_env",
                    "message": "Production target requires auth_token_env_name",
                }
            )
        elif not os.environ.get(target.auth_token_env_name, "").strip():
            issues.append(
                {
                    "level": LEVEL_ERROR,
                    "code": "production_token_missing",
                    "message": f"Env {target.auth_token_env_name} not set",
                }
            )
        if target.dry_run:
            issues.append(
                {
                    "level": LEVEL_WARN,
                    "code": "production_dry_run",
                    "message": "Production target has dry_run=true",
                }
            )

    if cls == TARGET_CLASS_TEST and target.enabled:
        issues.append(
            {
                "level": LEVEL_WARN,
                "code": "test_target_enabled",
                "message": "Test target should be disabled by default",
            }
        )

    auth_configured = False
    if target.auth_type in (None, "", "none"):
        auth_configured = True
    elif target.auth_token_env_name:
        auth_configured = bool(os.environ.get(target.auth_token_env_name, "").strip())

    return {
        "target_id": target.id,
        "name": target.name,
        "target_class": cls,
        "enabled": target.enabled,
        "dry_run": target.dry_run,
        "auth_type": target.auth_type,
        "auth_token_env_name": target.auth_token_env_name,
        "auth_configured": auth_configured,
        "endpoint_url": endpoint or None,
        "ignored_by_smoke": cls in (TARGET_CLASS_PRODUCTION, TARGET_CLASS_TEST) or not target.enabled,
        "ignored_by_default_health": should_ignore_in_default_health(target),
        "requires_production_flag": cls == TARGET_CLASS_PRODUCTION,
        "safe_for_smoke": cls == TARGET_CLASS_MOCK and not any(i["level"] == LEVEL_ERROR for i in issues),
        "issues": issues,
    }


def summarize_targets_safety(targets: list[PublishTarget]) -> dict[str, Any]:
    profiles = [validate_publish_target_safety(t) for t in targets]
    errors = [p for p in profiles if any(i["level"] == LEVEL_ERROR for i in p["issues"])]
    warns = [p for p in profiles if any(i["level"] == LEVEL_WARN for i in p["issues"]) and p not in errors]
    production = [p for p in profiles if p["target_class"] == TARGET_CLASS_PRODUCTION]
    mock = [p for p in profiles if p["target_class"] == TARGET_CLASS_MOCK]
    test = [p for p in profiles if p["target_class"] == TARGET_CLASS_TEST]
    return {
        "total": len(profiles),
        "mock_count": len(mock),
        "test_count": len(test),
        "production_count": len(production),
        "unsafe_count": len(errors),
        "warning_count": len(warns),
        "profiles": profiles,
        "unsafe_targets": [{"id": p["target_id"], "name": p["name"], "issues": p["issues"]} for p in errors],
    }
