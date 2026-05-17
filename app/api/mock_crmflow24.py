"""Mock crmflow24 inbound receiver ? testing only, not production CMS."""

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.publishers.validators import PAYLOAD_VERSION as ARTICLE_V1
from app.publishers.validators_v2 import (
    PAYLOAD_VERSION as ARTICLE_V2,
    validate_inbound_article_v2_payload,
)
from app.publishers.versions import SUPPORTED_PAYLOAD_FORMATS

router = APIRouter(prefix="/api/mock-crmflow24", tags=["mock-crmflow24"])

_MOCK_ARTICLES: list[dict[str, Any]] = []
_MOCK_FAIL_MODE = os.environ.get("MOCK_CRMFLOW24_FAIL_MODE", "")


class MockImportResponse(BaseModel):
    success: bool = True
    external_article_id: str
    draft_url: str
    status: str = "draft"
    payload_version: str | None = None
    response_schema_version: str = "crmflow24_ack_v2"


def _check_auth(authorization: str | None) -> None:
    expected = os.environ.get("CRMFLOW24_PUBLISH_TOKEN", "").strip()
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = authorization[7:].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def _validate_inbound_payload(payload: dict[str, Any]) -> None:
    version = payload.get("payload_version")
    if version not in SUPPORTED_PAYLOAD_FORMATS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_payload_version",
                "message": f"Unsupported payload_version: {version}",
                "supported": sorted(SUPPORTED_PAYLOAD_FORMATS),
            },
        )

    if version == ARTICLE_V2:
        result = validate_inbound_article_v2_payload(payload)
        if not result.valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_failed",
                    "issues": [{"field": e.field, "message": e.message} for e in result.errors],
                },
            )
        return

    if version == ARTICLE_V1:
        for field in ("title", "slug", "content_markdown", "seo"):
            if not payload.get(field):
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        return

    raise HTTPException(status_code=400, detail="Unknown payload version")


@router.post("/articles/import", response_model=MockImportResponse)
async def mock_import_article(
    request: Request,
    authorization: str | None = Header(default=None),
):
    _check_auth(authorization)

    if _MOCK_FAIL_MODE == "timeout":
        import asyncio
        await asyncio.sleep(120)

    if _MOCK_FAIL_MODE == "503":
        raise HTTPException(status_code=503, detail="Simulated upstream unavailable")

    if _MOCK_FAIL_MODE == "401":
        raise HTTPException(status_code=401, detail="Simulated unauthorized")

    if _MOCK_FAIL_MODE == "unsupported_version":
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_payload_version", "message": "article_v99 not supported"},
        )

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    _validate_inbound_payload(payload)

    article_num = len(_MOCK_ARTICLES) + 1
    external_id = f"crmflow24-{article_num}"
    draft_url = f"https://crmflow24.ru/drafts/{article_num}"

    record = {
        "external_article_id": external_id,
        "draft_url": draft_url,
        "status": "draft",
        "title": payload.get("title"),
        "slug": payload.get("slug"),
        "payload_version": payload.get("payload_version"),
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    _MOCK_ARTICLES.append(record)

    return MockImportResponse(
        external_article_id=external_id,
        draft_url=draft_url,
        status="draft",
        payload_version=str(payload.get("payload_version")),
    )


@router.get("/articles")
def mock_list_articles():
    return {
        "testing_only": True,
        "count": len(_MOCK_ARTICLES),
        "articles": list(_MOCK_ARTICLES),
    }


@router.delete("/articles")
def mock_reset_articles():
    _MOCK_ARTICLES.clear()
    return {"reset": True, "testing_only": True}
