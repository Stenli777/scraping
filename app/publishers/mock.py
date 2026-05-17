import json

from typing import Any

from app.models.publish_target import PublishTarget
from app.publishers.base import BasePublisher, PublisherResult


class MockPublisher(BasePublisher):
    """No HTTP — saves payload only (dry-run)."""

    def publish(
        self,
        target: PublishTarget,
        payload: dict[str, Any],
        *,
        dry_run: bool,
        timeout_seconds: int,
    ) -> PublisherResult:
        return PublisherResult(
            success=True,
            status="dry_run",
            dry_run=True,
            endpoint_url=target.endpoint_url,
            response_body=json.dumps({"mock": True, "received": True}, ensure_ascii=False),
            external_id=f"mock-{payload.get('meta', {}).get('scrap_document_id')}",
            metadata={"publisher": "mock"},
        )
