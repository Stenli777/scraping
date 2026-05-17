"""Parse inbound publish acknowledgment responses."""

from typing import Any

RESPONSE_SCHEMA_V1 = "crmflow24_ack_v1"
RESPONSE_SCHEMA_V2 = "crmflow24_ack_v2"


def detect_response_schema_version(data: dict[str, Any]) -> str:
    if data.get("external_article_id") is not None or data.get("success") is True:
        return RESPONSE_SCHEMA_V2
    return RESPONSE_SCHEMA_V1


def parse_publish_acknowledgment(data: dict[str, Any]) -> tuple[str | None, str | None, str | None, str]:
    """Return external_id, draft_url, remote_status, response_schema_version."""
    schema = detect_response_schema_version(data)

    external_id = (
        data.get("external_article_id")
        or data.get("external_id")
        or data.get("id")
        or data.get("article_id")
    )
    draft_url = data.get("draft_url") or data.get("url") or data.get("link")
    remote_status = data.get("status")

    if external_id is not None:
        external_id = str(external_id)
    if draft_url is not None:
        draft_url = str(draft_url)
    if remote_status is not None:
        remote_status = str(remote_status)

    if data.get("success") is False:
        return external_id, draft_url, remote_status, schema

    nested = data.get("data")
    if isinstance(nested, dict):
        ext2, url2, st2, _ = parse_publish_acknowledgment(nested)
        return external_id or ext2, draft_url or url2, remote_status or st2, schema

    return external_id, draft_url, remote_status, schema
