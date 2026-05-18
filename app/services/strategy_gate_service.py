"""Strategy quality gate, test document detection, strategy readiness."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_quality_review_enabled
from app.models.parsed_document import ParsedDocument
from app.services.publish_service import _latest_review
from app.services.quality_service import get_latest_quality_score

logger = logging.getLogger(__name__)

TEST_MARKERS: list[tuple[str, str]] = [
    ("smoke test scrap", "smoke_test"),
    ("smoke test", "smoke_test"),
    ("internal test", "internal_test"),
    ("тестовый", "internal_test"),
    ("удалить", "internal_test"),
    ("example.com", "smoke_test"),
    ("mock", "internal_test"),
    ("placeholder", "internal_test"),
    ("debug", "internal_test"),
]

STRATEGY_BLOCK_REASONS = frozenset({
    "smoke_test",
    "internal_test",
    "low_relevance",
    "blocked_topic",
    "low_quality",
    "missing_rewrite",
    "unknown",
})


def detect_test_document(*, title: str, text: str, slug: str = "") -> tuple[bool, str | None]:
    import re

    blob = f"{title}\n{text}\n{slug}".lower()
    title_slug = f"{title}\n{slug}".lower()
    boundary_markers = frozenset({"mock", "debug", "placeholder"})
    for marker, reason in TEST_MARKERS:
        if marker in boundary_markers:
            if re.search(rf"\b{re.escape(marker)}\b", title_slug):
                return True, reason
            continue
        if marker in blob:
            return True, reason
    return False, None


def compute_strategy_quality_score(extraction: dict[str, Any]) -> int:
    score = int(extraction.get("relevance_score") or 0)
    secondary = extraction.get("secondary_topics") or []
    if len(secondary) >= 2:
        score = min(100, score + 5)
    primary = str(extraction.get("primary_topic") or "")
    if primary and len(primary.split()) >= 2:
        score = min(100, score + 5)
    keywords = extraction.get("keywords") or []
    if len(keywords) >= 5:
        score = min(100, score + 3)
    if extraction.get("strategy_allowed") is False:
        score = min(score, 30)
    return max(0, min(100, score))


def merge_llm_topic_cleanup(deterministic: dict[str, Any], llm_data: dict[str, Any] | None) -> dict[str, Any]:
    if not llm_data:
        return dict(deterministic)
    merged = dict(deterministic)
    for key in (
        "primary_topic",
        "secondary_topics",
        "keywords",
        "entities",
        "search_intent",
        "relevance_score",
        "project_fit",
        "rejected_terms",
    ):
        val = llm_data.get(key)
        if val is None:
            continue
        if key in {"secondary_topics", "keywords", "entities", "rejected_terms"} and isinstance(val, list):
            merged[key] = [str(x) for x in val][:15]
        elif key == "relevance_score":
            try:
                merged[key] = max(0, min(100, int(val)))
            except (TypeError, ValueError):
                pass
        elif key in {"primary_topic", "search_intent", "project_fit"}:
            merged[key] = str(val)
    llm_warnings = llm_data.get("warnings")
    if isinstance(llm_warnings, list):
        warnings = list(merged.get("warnings") or [])
        warnings.extend(str(x) for x in llm_warnings)
        merged["warnings"] = warnings
    return merged


def apply_strategy_gate(
    db: Session,
    *,
    document: ParsedDocument,
    extraction: dict[str, Any],
    title: str,
    text_sample: str,
    slug: str = "",
) -> dict[str, Any]:
    settings = get_settings()
    threshold = settings.min_topic_relevance_for_strategy
    result = dict(extraction)
    warnings = list(result.get("warnings") or [])

    is_test, test_reason = detect_test_document(title=title, text=text_sample, slug=slug)
    result["is_test_document"] = is_test

    block_reason: str | None = None
    if is_test and test_reason:
        block_reason = test_reason
    elif not (document.rewritten_text and document.rewritten_text.strip()):
        block_reason = "missing_rewrite"
    else:
        review = _latest_review(db, document.id)
        meta = document.metadata_json or {}
        review_meta = meta.get("review") or {}
        take = review.take if review is not None else review_meta.get("take")
        if take is False:
            block_reason = "low_quality"
        elif is_quality_review_enabled():
            quality = get_latest_quality_score(db, document.id)
            if quality and quality.verdict == "rejected":
                block_reason = "low_quality"

        if block_reason is None:
            fit = str(result.get("project_fit") or "").lower()
            if fit and fit != "crmflow24":
                block_reason = "low_relevance"
            elif int(result.get("relevance_score") or 0) < threshold:
                rel = int(result.get("relevance_score") or 0)
                topic_blob = " ".join(
                    [
                        str(result.get("primary_topic") or ""),
                        " ".join(str(t) for t in (result.get("secondary_topics") or [])),
                        " ".join(str(k) for k in (result.get("keywords") or [])),
                    ]
                ).lower()
                crm_hint = any(
                    t in topic_blob
                    for t in ("bitrix", "битрикс", "crm", "воронк", "лид", "продаж", "телефон")
                )
                if take is True and rel >= 50 and crm_hint:
                    block_reason = None
                else:
                    block_reason = "low_relevance"

        if block_reason is None:
            llm_block = result.get("strategy_block_reason")
            if result.get("strategy_allowed") is False and llm_block in STRATEGY_BLOCK_REASONS:
                block_reason = str(llm_block)
            elif result.get("strategy_allowed") is False:
                block_reason = "blocked_topic"

    allowed = block_reason is None
    result["strategy_allowed"] = allowed
    result["strategy_block_reason"] = block_reason
    result["strategy_quality_score"] = compute_strategy_quality_score(result)
    if not allowed and block_reason:
        warnings.append(block_reason)
    result["warnings"] = warnings
    return result


def document_strategy_allowed(db: Session, document_id: int) -> tuple[bool, str | None, dict[str, Any]]:
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        return False, "unknown", {}
    topics = (doc.metadata_json or {}).get("topics") or {}
    if not topics:
        return False, "topic_not_extracted", topics
    if topics.get("strategy_allowed") is True:
        return True, None, topics
    return False, topics.get("strategy_block_reason") or "unknown", topics


def filter_strategy_document_ids(
    db: Session,
    doc_ids: list[int],
    *,
    include_blocked: bool = False,
) -> tuple[list[int], int, list[dict[str, Any]]]:
    if include_blocked:
        return doc_ids, 0, []
    allowed: list[int] = []
    excluded = 0
    excluded_details: list[dict[str, Any]] = []
    for did in doc_ids:
        ok, reason, topics = document_strategy_allowed(db, did)
        if ok:
            allowed.append(did)
        else:
            excluded += 1
            excluded_details.append({
                "document_id": did,
                "strategy_block_reason": reason,
                "is_test_document": topics.get("is_test_document"),
            })
    return allowed, excluded, excluded_details


def get_strategy_readiness(db: Session, document_id: int) -> dict[str, Any]:
    document = db.get(ParsedDocument, document_id)
    if not document:
        return {
            "ready": False,
            "missing": ["document"],
            "warnings": [],
            "checks": {},
        }

    meta = document.metadata_json or {}
    topics = meta.get("topics") or {}
    missing: list[str] = []
    warnings: list[str] = []

    review = _latest_review(db, document_id)
    review_meta = meta.get("review") or {}
    take = review.take if review is not None else review_meta.get("take")
    quality = get_latest_quality_score(db, document_id)
    quality_verdict = quality.verdict if quality else None

    title = meta.get("extracted_title") or meta.get("title") or ""
    text_sample = (document.rewritten_text or document.clean_text or "")[:500]
    is_test, test_reason = detect_test_document(title=title, text=text_sample)

    checks: dict[str, Any] = {
        "topic_extracted": bool(topics),
        "strategy_allowed": topics.get("strategy_allowed") if topics else False,
        "relevance_score": topics.get("relevance_score") if topics else None,
        "review_take": take,
        "quality_verdict": quality_verdict,
        "is_test_document": topics.get("is_test_document", is_test),
        "strategy_block_reason": topics.get("strategy_block_reason"),
        "strategy_quality_score": topics.get("strategy_quality_score"),
        "llm_cleanup_status": topics.get("llm_cleanup_status"),
    }

    if not topics:
        missing.append("topic_extracted")
    elif topics.get("strategy_allowed") is not True:
        missing.append("strategy_blocked")
        br = topics.get("strategy_block_reason") or test_reason
        if br:
            warnings.append(str(br))

    if is_test and test_reason and test_reason not in warnings:
        warnings.append(test_reason)

    for item in topics.get("warnings") or []:
        if item not in warnings:
            warnings.append(str(item))

    ready = len(missing) == 0
    return {
        "ready": ready,
        "missing": missing,
        "warnings": warnings,
        "checks": checks,
    }
