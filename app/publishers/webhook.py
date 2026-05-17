import json
import logging
import os
import re
from typing import Any

import httpx

from app.models.publish_target import PublishTarget
from app.publishers.base import BasePublisher, PublisherResult
from app.publishers.exceptions import (
    PublishAuthError,
    PublishClientError,
    PublishServerError,
    PublishTransportError,
    PublishUnsupportedPayloadError,
)
from app.publishers.response_parser import parse_publish_acknowledgment
from app.publishers.versions import SUPPORTED_PAYLOAD_FORMATS

logger = logging.getLogger(__name__)

MAX_RESPONSE_BODY = 8000
REDACT_PATTERNS = (
    re.compile(r"(Bearer\s+)\S+", re.IGNORECASE),
    re.compile(r"(X-API-Key:\s*)\S+", re.IGNORECASE),
    re.compile(r'("authorization"\s*:\s*")[^"]+', re.IGNORECASE),
)


def _redact_sensitive(text: str) -> str:
    out = text
    for pattern in REDACT_PATTERNS:
        out = pattern.sub(r"\1***", out)
    return out


def _resolve_auth_header(target: PublishTarget) -> dict[str, str]:
    if target.auth_type == "none" or not target.auth_type:
        return {}
    if not target.auth_token_env_name:
        raise PublishAuthError("auth_token_env_name is required for authenticated targets")

    token = os.environ.get(target.auth_token_env_name, "").strip()
    if not token:
        raise PublishAuthError(f"Env variable {target.auth_token_env_name} is not set")

    if target.auth_type == "bearer":
        return {"Authorization": f"Bearer {token}"}
    if target.auth_type == "api_key":
        return {"X-API-Key": token}
    raise PublishAuthError(f"Unsupported auth_type: {target.auth_type}")


def _truncate_body(text: str | None) -> str | None:
    if not text:
        return text
    if len(text) <= MAX_RESPONSE_BODY:
        return text
    return text[:MAX_RESPONSE_BODY] + "?"


class WebhookPublisher(BasePublisher):
    def publish(
        self,
        target: PublishTarget,
        payload: dict[str, Any],
        *,
        dry_run: bool,
        timeout_seconds: int,
    ) -> PublisherResult:
        payload_version = str(payload.get("payload_version") or "")
        if payload_version and payload_version not in SUPPORTED_PAYLOAD_FORMATS:
            raise PublishUnsupportedPayloadError(
                f"Unsupported payload_version for webhook: {payload_version}"
            )

        endpoint = (getattr(target, "endpoint_url", None) or "").strip()
        if dry_run or target.dry_run:
            endpoint = endpoint or "(dry-run)"
            preview = {
                "dry_run": True,
                "payload_version": payload.get("payload_version"),
                "title": payload.get("title"),
                "slug": payload.get("slug"),
            }
            return PublisherResult(
                success=True,
                status="dry_run",
                dry_run=True,
                endpoint_url=endpoint,
                response_body=json.dumps(preview, ensure_ascii=False),
                metadata={"publisher": "webhook", "skipped_http": True},
            )

        if not endpoint:
            raise PublishTransportError("Publish endpoint URL is not configured")

        headers = {"Content-Type": "application/json", **_resolve_auth_header(target)}
        doc_id = payload.get("meta", {}).get("scrap_document_id") or payload.get("source", {}).get(
            "document_id"
        )

        last_exc: Exception | None = None
        response = None
        for attempt in range(2):
            try:
                with httpx.Client(timeout=timeout_seconds) as client:
                    response = client.post(endpoint, json=payload, headers=headers)
                last_exc = None
                break
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt == 0:
                    logger.warning(
                        "Webhook publish timeout (retry) target=%s document=%s",
                        target.id,
                        doc_id,
                    )
                    continue
                raise PublishTransportError(
                    f"Publish timeout after {timeout_seconds}s"
                ) from exc
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == 0:
                    logger.warning(
                        "Webhook publish network error (retry) target=%s: %s",
                        target.id,
                        _redact_sensitive(str(exc)),
                    )
                    continue
                raise PublishTransportError(_redact_sensitive(str(exc))) from exc

        if last_exc or response is None:
            raise PublishTransportError(str(last_exc or "No response"))

        body = _truncate_body(_redact_sensitive(response.text))
        logger.info(
            "Webhook publish target=%s http=%s document=%s",
            target.id,
            response.status_code,
            doc_id,
        )

        if 200 <= response.status_code < 300:
            external_id = None
            draft_url = None
            remote_status = None
            response_schema_version = None
            try:
                data = response.json()
                if isinstance(data, dict):
                    external_id, draft_url, remote_status, response_schema_version = (
                        parse_publish_acknowledgment(data)
                    )
            except Exception:
                pass
            return PublisherResult(
                success=True,
                status=remote_status or "success",
                dry_run=False,
                endpoint_url=endpoint,
                response_status_code=response.status_code,
                response_body=body,
                external_id=external_id or None,
                draft_url=draft_url,
                metadata={
                    "publisher": "webhook",
                    "remote_status": remote_status,
                    "response_schema_version": response_schema_version,
                },
            )

        if response.status_code in (401, 403):
            raise PublishClientError(
                f"HTTP {response.status_code}: unauthorized"
            )

        if 400 <= response.status_code < 500:
            detail = (body or "")[:200]
            if "unsupported" in detail.lower() or "payload_version" in detail.lower():
                raise PublishUnsupportedPayloadError(
                    f"HTTP {response.status_code}: {detail}"
                )
            raise PublishClientError(f"HTTP {response.status_code}: {detail}")

        raise PublishServerError(f"HTTP {response.status_code}: {(body or '')[:200]}")
