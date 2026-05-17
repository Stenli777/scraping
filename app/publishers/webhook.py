import json
import logging
import os
from typing import Any

import httpx

from app.models.publish_target import PublishTarget
from app.publishers.base import BasePublisher, PublisherResult
from app.publishers.exceptions import (
    PublishAuthError,
    PublishClientError,
    PublishServerError,
    PublishTransportError,
)

logger = logging.getLogger(__name__)

MAX_RESPONSE_BODY = 8000


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
    return text[:MAX_RESPONSE_BODY] + "…"


class WebhookPublisher(BasePublisher):
    def publish(
        self,
        target: PublishTarget,
        payload: dict[str, Any],
        *,
        dry_run: bool,
        timeout_seconds: int,
    ) -> PublisherResult:
        endpoint = (target.endpoint_url or "").strip()
        if not endpoint:
            raise PublishClientError("endpoint_url is required for webhook publish")

        if dry_run or target.dry_run:
            return PublisherResult(
                success=True,
                status="dry_run",
                dry_run=True,
                endpoint_url=endpoint,
                response_body=json.dumps({"dry_run": True}, ensure_ascii=False),
                metadata={"publisher": "webhook", "skipped_http": True},
            )

        headers = {"Content-Type": "application/json", **_resolve_auth_header(target)}

        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise PublishTransportError(f"Publish timeout after {timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            raise PublishTransportError(str(exc)) from exc

        body = _truncate_body(response.text)
        logger.info(
            "Webhook publish target=%s status=%s document=%s",
            target.id,
            response.status_code,
            payload.get("meta", {}).get("scrap_document_id"),
        )

        if 200 <= response.status_code < 300:
            external_id = None
            try:
                data = response.json()
                external_id = str(data.get("id") or data.get("external_id") or "")
            except Exception:
                pass
            return PublisherResult(
                success=True,
                status="success",
                dry_run=False,
                endpoint_url=endpoint,
                response_status_code=response.status_code,
                response_body=body,
                external_id=external_id or None,
                metadata={"publisher": "webhook"},
            )

        if 400 <= response.status_code < 500:
            raise PublishClientError(f"HTTP {response.status_code}: {body[:200] if body else ''}")

        raise PublishServerError(f"HTTP {response.status_code}: {body[:200] if body else ''}")
