"""Deterministic source quality intelligence — discovery anti-noise layer.

Core pipeline NEVER depends on quality scoring completion.
Scoring failure MUST NOT block discovery storage; URLs are never deleted.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import DiscoveredUrlStatus
from app.core.feature_flags import is_discovery_quality_scoring_enabled
from app.models.discovered_url import DiscoveredUrl
from app.models.domain_trust_registry import DomainTrustRegistry
from app.models.parsed_document import ParsedDocument
from app.models.source_quality_score import SourceQualityScore
from app.services.url_normalizer import normalize_url

logger = logging.getLogger(__name__)

SCORING_VERSION = "source_quality_v1"

AI_SPAM_PHRASES = [
    "in today's rapidly evolving digital landscape",
    "it is important to note",
    "in conclusion",
    "delve into",
    "game-changer",
    "unlock the power",
    "comprehensive guide",
    "ultimate guide",
    "you need to know",
    "leverage the power",
    "cutting-edge solutions",
    "revolutionize your",
    "seamlessly integrate",
    "robust solution",
    "holistic approach",
]

CLICKBAIT_PATTERNS = [
    r"\b(top\s+\d+|лучших\s+\d+|топ[\s-]?\d+)",
    r"\b(шокирующ|невероятн|секретн).{0,20}(способ|метод)",
    r"\byou won't believe\b",
    r"\bmust read\b",
]

JUNK_PATH_SEGMENTS = frozenset({
    "tag", "tags", "category", "categories", "author", "page", "feed",
    "wp-content", "attachment", "search", "filter",
})

CRM_TERMS = frozenset({
    "crm", "битрикс", "bitrix", "bitrix24", "продаж", "лид", "воронк",
    "интеграц", "автоматизац", "клиент", "b2b", "saas",
})

BLOCKED_DOMAIN_SUFFIXES = (".xyz", ".top", ".click", ".loan", ".work")


@dataclass
class QualitySignals:
    word_count: int = 0
    heading_count: int = 0
    link_count: int = 0
    crm_term_hits: int = 0
    ai_phrase_hits: int = 0
    clickbait_hits: int = 0
    path_junk: bool = False
    fetch_ok: bool = False
    warnings: list[str] = field(default_factory=list)
    positives: list[str] = field(default_factory=list)


def _extract_domain(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().lstrip("www.")
    except Exception:
        return ""


def _count_words(text: str) -> int:
    tokens = re.findall(r"[\w\u0400-\u04ff]{2,}", text.lower())
    return len(tokens)


def _fetch_preview(url: str) -> tuple[str, int | None]:
    settings = get_settings()
    try:
        with httpx.Client(timeout=settings.discovery_quality_fetch_timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": settings.http_user_agent})
            return resp.text[:50000], resp.status_code
    except Exception as exc:
        logger.debug("quality preview fetch failed %s: %s", url, exc)
        return "", None


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def get_domain_trust_score(db: Session, domain: str, project_id: int | None) -> int:
    if not domain:
        return 50
    for d in (domain, f"www.{domain}"):
        if project_id is not None:
            row = db.scalar(
                select(DomainTrustRegistry).where(
                    DomainTrustRegistry.domain == d,
                    DomainTrustRegistry.project_id == project_id,
                ).limit(1)
            )
            if row:
                return int(row.trust_score)
        row = db.scalar(
            select(DomainTrustRegistry).where(
                DomainTrustRegistry.domain == d,
                DomainTrustRegistry.project_id.is_(None),
            ).limit(1)
        )
        if row:
            return int(row.trust_score)
    if domain.endswith(BLOCKED_DOMAIN_SUFFIXES):
        return 15
    if "habr.com" in domain or "saltpro.ru" in domain:
        return 80
    return 50


def analyze_signals(
    *,
    url: str,
    title: str | None,
    text: str,
    domain: str,
) -> QualitySignals:
    sig = QualitySignals()
    blob = f"{title or ''} {text}".lower()
    sig.word_count = _count_words(blob)
    sig.heading_count = len(re.findall(r"<h[1-6]", text, re.I)) if "<" in text else len(
        re.findall(r"^#{1,3}\s", text, re.M)
    )
    sig.link_count = len(re.findall(r"<a\s", text, re.I)) if "<" in text else blob.count("http")
    sig.crm_term_hits = sum(1 for t in CRM_TERMS if t in blob)
    sig.ai_phrase_hits = sum(1 for p in AI_SPAM_PHRASES if p in blob)
    for pat in CLICKBAIT_PATTERNS:
        if re.search(pat, blob, re.I):
            sig.clickbait_hits += 1
    path = urlparse(url).path.lower().strip("/")
    parts = path.split("/") if path else []
    if parts and parts[0] in JUNK_PATH_SEGMENTS:
        sig.path_junk = True
    if any(x in url.lower() for x in ("/page/", "/tag/", "/category/", "?page=")):
        sig.path_junk = True
    return sig


def score_signals(
    sig: QualitySignals,
    *,
    trust_score: int,
    title: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    details: dict[str, Any] = {"warnings": [], "positives": []}

    thin = 0
    if sig.word_count < 300:
        thin += min(90, 100 - sig.word_count // 3)
    if sig.heading_count == 0 and sig.word_count > 50:
        thin += 25
    if sig.link_count > 40:
        thin += 20
    if sig.word_count > 0 and sig.link_count / max(sig.word_count, 1) > 0.15:
        thin += 15
    thin_content_score = min(100, thin)

    ai_noise = min(100, sig.ai_phrase_hits * 22 + (10 if sig.clickbait_hits else 0))
    spam = min(100, sig.clickbait_hits * 35 + sig.path_junk * 40 + (30 if trust_score < 25 else 0))

    relevance = 40
    if sig.crm_term_hits >= 3:
        relevance += 35
        details["positives"].append("crm_terminology")
    elif sig.crm_term_hits >= 1:
        relevance += 15
    if trust_score >= 75:
        relevance += 15
        details["positives"].append("trusted_domain")
    if title and len(title.split()) >= 4:
        relevance += 10
    relevance = min(100, relevance)

    quality = int(
        0.25 * trust_score
        + 0.30 * relevance
        + 0.20 * min(100, sig.word_count // 8)
        + 0.15 * min(100, sig.heading_count * 12)
        - 0.15 * thin_content_score
        - 0.10 * ai_noise
        - 0.10 * spam
    )
    quality = max(0, min(100, quality))

    if thin_content_score >= settings.max_thin_content_score_block:
        details["warnings"].append("thin_content")
    if ai_noise >= 50:
        details["warnings"].append("ai_noise")
    if spam >= settings.max_spam_score_block:
        details["warnings"].append("spam_heavy")
    if relevance < settings.min_source_relevance_score:
        details["warnings"].append("low_relevance")
    if sig.path_junk:
        details["warnings"].append("junk_path")

    return {
        "quality_score": quality,
        "relevance_score": relevance,
        "trust_score": trust_score,
        "spam_score": spam,
        "thin_content_score": thin_content_score,
        "ai_noise_score": ai_noise,
        "scoring_details": details,
    }


def compute_duplicate_risk(
    db: Session,
    *,
    url: str,
    title: str | None,
    project_id: int,
    discovered_url_id: int | None,
) -> tuple[int, list[str]]:
    warnings: list[str] = []
    try:
        normalized = normalize_url(url)
    except ValueError:
        return 0, warnings

    title_norm = (title or "").strip().lower()
    risk = 0

    others = db.scalars(
        select(DiscoveredUrl)
        .where(DiscoveredUrl.project_id == project_id)
        .where(DiscoveredUrl.id != (discovered_url_id or -1))
        .limit(200)
    ).all()
    for other in others:
        if other.normalized_url == normalized:
            risk = max(risk, 95)
            warnings.append(f"duplicate_url:{other.id}")
        elif title_norm and other.title:
            sim = SequenceMatcher(None, title_norm, other.title.lower()).ratio()
            if sim >= 0.88:
                risk = max(risk, int(sim * 100))
                warnings.append(f"similar_title:{other.id}")

    for doc in db.scalars(select(ParsedDocument).limit(100)).all():
        if doc.source_url and normalize_url(doc.source_url) == normalized:
            risk = max(risk, 90)
            warnings.append(f"existing_document:{doc.id}")
    return min(100, risk), warnings


def apply_quality_gate(scores: dict[str, Any], duplicate_risk: int) -> tuple[bool, str | None]:
    settings = get_settings()
    if duplicate_risk >= settings.max_duplicate_risk_block:
        return False, "duplicate_risk"
    if scores["spam_score"] >= settings.max_spam_score_block:
        return False, "spam_high"
    if scores["thin_content_score"] >= settings.max_thin_content_score_block:
        return False, "thin_content"
    if scores["relevance_score"] < settings.min_source_relevance_score:
        return False, "low_relevance"
    if scores["quality_score"] < settings.min_source_quality_score:
        return False, "low_quality"
    if scores["trust_score"] < 20:
        return False, "blocked_domain"
    return True, None


def score_discovered_url(
    db: Session,
    discovered_url_id: int,
    *,
    fetch_preview: bool | None = None,
    persist: bool = True,
) -> SourceQualityScore:
    record = db.get(DiscoveredUrl, discovered_url_id)
    if not record:
        raise ValueError(f"Discovered URL {discovered_url_id} not found")

    settings = get_settings()
    do_fetch = fetch_preview if fetch_preview is not None else settings.discovery_quality_fetch_preview

    domain = _extract_domain(record.url)
    text = ""
    if do_fetch:
        html, status = _fetch_preview(record.url)
        if html:
            text = _strip_html(html)
            if status and status >= 400:
                text = ""
    title = record.title or ""

    trust = get_domain_trust_score(db, domain, record.project_id)
    sig = analyze_signals(url=record.url, title=title, text=text, domain=domain)
    sig.fetch_ok = bool(text)
    scored = score_signals(sig, trust_score=trust, title=title)
    dup_risk, dup_warn = compute_duplicate_risk(
        db, url=record.url, title=title, project_id=record.project_id, discovered_url_id=record.id
    )

    scores = {**scored, "duplicate_risk_score": dup_risk}
    details = scored["scoring_details"]
    details["duplicate_warnings"] = dup_warn
    details["word_count"] = sig.word_count
    details["fetch_preview"] = do_fetch and sig.fetch_ok

    allowed, block_reason = apply_quality_gate(scores, dup_risk)

    row = SourceQualityScore(
        project_id=record.project_id,
        source_directory_id=record.source_directory_id,
        discovered_url_id=record.id,
        url=record.url,
        domain=domain,
        quality_score=scores["quality_score"],
        relevance_score=scores["relevance_score"],
        trust_score=scores["trust_score"],
        spam_score=scores["spam_score"],
        thin_content_score=scores["thin_content_score"],
        ai_noise_score=scores["ai_noise_score"],
        duplicate_risk_score=dup_risk,
        language_detected="ru" if re.search(r"[\u0400-\u04ff]", title + text) else "en",
        strategy_allowed=allowed,
        strategy_block_reason=block_reason,
        scoring_version=SCORING_VERSION,
        scoring_details_json=details,
    )
    if persist:
        db.add(row)
        if is_discovery_quality_scoring_enabled():
            if allowed or record.status == DiscoveredUrlStatus.MANUALLY_APPROVED.value:
                if record.status != DiscoveredUrlStatus.MANUALLY_APPROVED.value:
                    record.status = DiscoveredUrlStatus.QUALITY_SCORED.value
            else:
                record.status = DiscoveredUrlStatus.QUALITY_BLOCKED.value
        db.flush()
    return row


def latest_quality_for_discovered(db: Session, discovered_url_id: int) -> SourceQualityScore | None:
    return db.scalar(
        select(SourceQualityScore)
        .where(SourceQualityScore.discovered_url_id == discovered_url_id)
        .order_by(SourceQualityScore.id.desc())
        .limit(1)
    )


def can_enqueue_by_quality(db: Session, record: DiscoveredUrl) -> tuple[bool, str | None]:
    if record.status == DiscoveredUrlStatus.MANUALLY_APPROVED.value:
        return True, None
    if record.status == DiscoveredUrlStatus.QUALITY_BLOCKED.value:
        q = latest_quality_for_discovered(db, record.id)
        if q and q.manual_override:
            return True, None
        return False, "quality_blocked"
    if not is_discovery_quality_scoring_enabled():
        return True, None
    q = latest_quality_for_discovered(db, record.id)
    if not q:
        return False, "quality_not_scored"
    if q.manual_override or q.strategy_allowed:
        return True, None
    return False, q.strategy_block_reason or "quality_gate"


def approve_discovered_url_quality(
    db: Session,
    discovered_url_id: int,
    *,
    approved_by: str = "operator",
    note: str | None = None,
) -> DiscoveredUrl:
    record = db.get(DiscoveredUrl, discovered_url_id)
    if not record:
        raise ValueError("Discovered URL not found")
    record.status = DiscoveredUrlStatus.MANUALLY_APPROVED.value
    q = latest_quality_for_discovered(db, discovered_url_id)
    if q:
        q.strategy_allowed = True
        q.strategy_block_reason = None
        q.manual_override = True
        details = dict(q.scoring_details_json or {})
        details["manual_approve"] = {"by": approved_by, "note": note}
        q.scoring_details_json = details
    else:
        score_discovered_url(db, discovered_url_id, fetch_preview=False)
        q = latest_quality_for_discovered(db, discovered_url_id)
        if q:
            q.strategy_allowed = True
            q.manual_override = True
            q.strategy_block_reason = None
    db.flush()
    return record


def quality_to_dict(q: SourceQualityScore) -> dict[str, Any]:
    return {
        "id": q.id,
        "discovered_url_id": q.discovered_url_id,
        "quality_score": q.quality_score,
        "relevance_score": q.relevance_score,
        "trust_score": q.trust_score,
        "spam_score": q.spam_score,
        "thin_content_score": q.thin_content_score,
        "ai_noise_score": q.ai_noise_score,
        "duplicate_risk_score": q.duplicate_risk_score,
        "strategy_allowed": q.strategy_allowed,
        "strategy_block_reason": q.strategy_block_reason,
        "manual_override": q.manual_override,
        "scoring_version": q.scoring_version,
        "warnings": (q.scoring_details_json or {}).get("warnings", []),
    }
