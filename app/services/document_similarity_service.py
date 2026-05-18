"""Deterministic document similarity, canonical groups, rewrite lineage (no embeddings)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.campaign_document_link import CampaignDocumentLink
from app.models.canonical_content_group import CanonicalContentGroup
from app.models.document_revision import DocumentRevision
from app.models.document_similarity_link import DocumentSimilarityLink
from app.models.parsed_document import ParsedDocument
from app.models.rewrite_lineage import RewriteLineage
from app.models.scraping_task import ScrapingTask
from app.models.seo_metadata import SeoMetadata
from app.services.campaign_service import _document_publish_state, normalize_keyword, tokenize

SIMILARITY_SAME_SOURCE = "same_source"
SIMILARITY_NEAR_DUPLICATE = "near_duplicate"
SIMILARITY_TOPIC_OVERLAP = "topic_overlap"
SIMILARITY_REWRITE_FAMILY = "rewrite_family"
SIMILARITY_CAMPAIGN_OVERLAP = "campaign_overlap"
SIMILARITY_CROSS_SOURCE = "cross_source_overlap"

STRATEGY_MERGE_TOPICS = "merge_topics"
STRATEGY_REWRITE_ANGLE = "rewrite_angle_needed"
STRATEGY_PUBLISH_SAFE = "publish_safe"
STRATEGY_CAMPAIGN_OVERLAP = "campaign_overlap_warning"
STRATEGY_DUPLICATE_CANDIDATE = "duplicate_candidate"
STRATEGY_CANONICALIZE = "canonicalize_existing"

_LINEAGE_SOURCE = "source_scrape"
_LINEAGE_REWRITE = "source_rewrite"
_LINEAGE_REVISION = "document_revision"
_LINEAGE_REPUBLICATION = "republication"


def _pair_ids(a: int, b: int) -> tuple[int, int]:
    return (min(a, b), max(a, b))


def _normalize_url(url: str) -> str:
    u = (url or "").strip().lower()
    if not u:
        return ""
    parsed = urlparse(u)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.netloc}{path}"


def _slug_similarity(slug_a: str, slug_b: str) -> float:
    if not slug_a or not slug_b:
        return 0.0
    return SequenceMatcher(None, normalize_keyword(slug_a), normalize_keyword(slug_b)).ratio()


def _text_overlap_ratio(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def _rewrite_snippet_overlap(text_a: str | None, text_b: str | None, *, limit: int = 1200) -> float:
    ta = (text_a or "").strip()[:limit]
    tb = (text_b or "").strip()[:limit]
    if not ta or not tb:
        return 0.0
    return SequenceMatcher(None, ta, tb).ratio()


def _heading_tokens(meta: dict) -> set[str]:
    headings = meta.get("headings") or meta.get("structure", {}).get("headings") or []
    tokens: set[str] = set()
    if isinstance(headings, list):
        for h in headings:
            if isinstance(h, str):
                tokens |= tokenize(h)
            elif isinstance(h, dict):
                tokens |= tokenize(str(h.get("text") or h.get("title") or ""))
    return tokens


def _document_features(db: Session, document_id: int) -> dict[str, Any]:
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    meta = doc.metadata_json or {}
    seo = db.scalar(
        select(SeoMetadata).where(SeoMetadata.document_id == document_id).order_by(SeoMetadata.id.desc())
    )
    title = (seo.h1 if seo else None) or (seo.seo_title if seo else None) or meta.get("title") or ""
    slug = (seo.slug if seo else None) or ""
    topics = (meta.get("topics") or {}).get("keywords") or []
    tags = (seo.tags_json if seo else None) or []
    keywords = {normalize_keyword(k) for k in topics + tags if k}
    keywords |= tokenize(title) | tokenize(slug)
    topic_primary = (meta.get("topics") or {}).get("primary_topic") or meta.get("primary_topic") or ""
    task = doc.task
    source_id = task.source_id if task else None
    source_url_norm = _normalize_url(doc.source_url or "")
    campaign_ids = list(
        db.scalars(
            select(CampaignDocumentLink.campaign_id).where(CampaignDocumentLink.document_id == document_id)
        ).all()
    )
    return {
        "doc": doc,
        "title": title,
        "slug": slug,
        "keywords": keywords,
        "headings": _heading_tokens(meta),
        "topic_primary": normalize_keyword(str(topic_primary)) if topic_primary else "",
        "source_id": source_id,
        "source_url_norm": source_url_norm,
        "rewritten_text": doc.rewritten_text,
        "canonical_group_id": doc.canonical_group_id,
        "campaign_ids": set(campaign_ids),
        "publish_state": _document_publish_state(db, document_id),
    }


def _composite_score(
    *,
    title_sim: float,
    slug_sim: float,
    keyword_overlap: float,
    topic_overlap: float,
    heading_overlap: float,
    rewrite_overlap: float,
) -> int:
    weighted = (
        title_sim * 0.28
        + slug_sim * 0.12
        + keyword_overlap * 0.22
        + topic_overlap * 0.18
        + heading_overlap * 0.08
        + rewrite_overlap * 0.12
    )
    return min(100, max(0, int(round(weighted * 100))))


def _classify_similarity_type(
    fa: dict[str, Any],
    fb: dict[str, Any],
    *,
    title_sim: float,
    keyword_overlap: float,
    topic_overlap: float,
    rewrite_overlap: float,
    composite: int,
) -> str:
    settings = get_settings()
    if fa["source_url_norm"] and fa["source_url_norm"] == fb["source_url_norm"]:
        return SIMILARITY_SAME_SOURCE
    if fa["source_id"] and fa["source_id"] == fb["source_id"] and composite >= settings.similarity_topic_overlap_threshold:
        return SIMILARITY_SAME_SOURCE
    if fa["campaign_ids"] & fb["campaign_ids"] and composite >= settings.similarity_topic_overlap_threshold:
        return SIMILARITY_CAMPAIGN_OVERLAP
    if rewrite_overlap >= 0.72 or (
        rewrite_overlap >= 0.55 and composite >= settings.similarity_near_duplicate_threshold
    ):
        return SIMILARITY_REWRITE_FAMILY
    if composite >= settings.similarity_near_duplicate_threshold:
        return SIMILARITY_NEAR_DUPLICATE
    if topic_overlap >= 0.5 or composite >= settings.similarity_topic_overlap_threshold:
        return SIMILARITY_TOPIC_OVERLAP
    return SIMILARITY_CROSS_SOURCE


def _duplicate_risk_level(composite: int, similarity_type: str) -> str:
    if similarity_type in (SIMILARITY_SAME_SOURCE, SIMILARITY_NEAR_DUPLICATE):
        if composite >= 90:
            return "critical"
        if composite >= 80:
            return "high"
        return "medium"
    if composite >= 75:
        return "medium"
    if composite >= 60:
        return "low"
    return "low"


def _strategy_action_for(
    similarity_type: str,
    duplicate_risk: str,
    *,
    both_published: bool,
    same_group_published: bool,
) -> str:
    if similarity_type == SIMILARITY_CAMPAIGN_OVERLAP:
        return STRATEGY_CAMPAIGN_OVERLAP
    if similarity_type in (SIMILARITY_SAME_SOURCE, SIMILARITY_NEAR_DUPLICATE):
        if both_published or same_group_published:
            return STRATEGY_CANONICALIZE
        return STRATEGY_DUPLICATE_CANDIDATE
    if similarity_type == SIMILARITY_REWRITE_FAMILY:
        return STRATEGY_REWRITE_ANGLE
    if similarity_type == SIMILARITY_TOPIC_OVERLAP and duplicate_risk in ("high", "critical"):
        return STRATEGY_MERGE_TOPICS
    if duplicate_risk in ("high", "critical"):
        return STRATEGY_REWRITE_ANGLE
    return STRATEGY_PUBLISH_SAFE


def compare_document_pair(db: Session, document_id_a: int, document_id_b: int) -> dict[str, Any]:
    if document_id_a == document_id_b:
        raise ValueError("Cannot compare document to itself")
    fa = _document_features(db, document_id_a)
    fb = _document_features(db, document_id_b)
    title_sim = SequenceMatcher(
        None, normalize_keyword(fa["title"]), normalize_keyword(fb["title"])
    ).ratio()
    slug_sim = _slug_similarity(fa["slug"], fb["slug"])
    keyword_overlap = _text_overlap_ratio(fa["keywords"], fb["keywords"])
    topic_overlap = 1.0 if fa["topic_primary"] and fa["topic_primary"] == fb["topic_primary"] else keyword_overlap
    heading_overlap = _text_overlap_ratio(fa["headings"], fb["headings"])
    rewrite_overlap = _rewrite_snippet_overlap(fa["rewritten_text"], fb["rewritten_text"])
    composite = _composite_score(
        title_sim=title_sim,
        slug_sim=slug_sim,
        keyword_overlap=keyword_overlap,
        topic_overlap=topic_overlap,
        heading_overlap=heading_overlap,
        rewrite_overlap=rewrite_overlap,
    )
    similarity_type = _classify_similarity_type(
        fa,
        fb,
        title_sim=title_sim,
        keyword_overlap=keyword_overlap,
        topic_overlap=topic_overlap,
        rewrite_overlap=rewrite_overlap,
        composite=composite,
    )
    duplicate_risk = _duplicate_risk_level(composite, similarity_type)
    both_published = fa["publish_state"] == "published" and fb["publish_state"] == "published"
    same_group_published = bool(
        fa["canonical_group_id"]
        and fa["canonical_group_id"] == fb["canonical_group_id"]
        and both_published
    )
    strategy_action = _strategy_action_for(
        similarity_type,
        duplicate_risk,
        both_published=both_published,
        same_group_published=same_group_published,
    )
    return {
        "document_id_a": document_id_a,
        "document_id_b": document_id_b,
        "similarity_score": composite,
        "similarity_type": similarity_type,
        "title_similarity": round(title_sim, 4),
        "keyword_overlap": round(keyword_overlap, 4),
        "topic_overlap": round(topic_overlap, 4),
        "rewrite_overlap": round(rewrite_overlap, 4),
        "duplicate_risk": duplicate_risk,
        "strategy_action": strategy_action,
        "details": {
            "slug_similarity": round(slug_sim, 4),
            "heading_overlap": round(heading_overlap, 4),
            "both_published": both_published,
        },
    }


def _resolve_project_id(db: Session, document_id: int) -> int | None:
    doc = db.get(ParsedDocument, document_id)
    if not doc or not doc.task:
        return None
    from app.services.project_profile_service import resolve_task_project

    project = resolve_task_project(db, doc.task)
    return project.id if project else None


def _candidate_document_ids(db: Session, *, project_id: int, document_id: int, limit: int) -> list[int]:
    rows = db.scalars(
        select(ParsedDocument.id)
        .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
        .where(ScrapingTask.project_id == project_id, ParsedDocument.id != document_id)
        .order_by(ParsedDocument.id.desc())
        .limit(limit)
    ).all()
    return list(rows)


def upsert_similarity_link(db: Session, project_id: int, comparison: dict[str, Any]) -> DocumentSimilarityLink:
    doc_a, doc_b = _pair_ids(comparison["document_id_a"], comparison["document_id_b"])
    link = db.scalar(
        select(DocumentSimilarityLink).where(
            DocumentSimilarityLink.project_id == project_id,
            DocumentSimilarityLink.document_id_a == doc_a,
            DocumentSimilarityLink.document_id_b == doc_b,
        )
    )
    if not link:
        link = DocumentSimilarityLink(
            project_id=project_id,
            document_id_a=doc_a,
            document_id_b=doc_b,
        )
        db.add(link)
    link.similarity_score = comparison["similarity_score"]
    link.similarity_type = comparison["similarity_type"]
    link.title_similarity = comparison["title_similarity"]
    link.keyword_overlap = comparison["keyword_overlap"]
    link.topic_overlap = comparison["topic_overlap"]
    link.rewrite_overlap = comparison["rewrite_overlap"]
    link.duplicate_risk = comparison["duplicate_risk"]
    link.strategy_action = comparison["strategy_action"]
    link.details_json = comparison.get("details")
    return link


def suggest_canonical_group(
    db: Session,
    *,
    project_id: int,
    document_id: int,
    comparisons: list[dict[str, Any]],
) -> CanonicalContentGroup | None:
    settings = get_settings()
    strong = [
        c
        for c in comparisons
        if c["similarity_score"] >= settings.similarity_near_duplicate_threshold
        or c["similarity_type"] in (SIMILARITY_SAME_SOURCE, SIMILARITY_NEAR_DUPLICATE, SIMILARITY_REWRITE_FAMILY)
    ]
    if not strong:
        return None

    doc = db.get(ParsedDocument, document_id)
    if not doc:
        return None

    partner_ids = []
    for c in strong:
        partner_ids.append(c["document_id_b"] if c["document_id_a"] == document_id else c["document_id_a"])
    group_ids = set()
    for pid in partner_ids:
        pdoc = db.get(ParsedDocument, pid)
        if pdoc and pdoc.canonical_group_id:
            group_ids.add(pdoc.canonical_group_id)
    if doc.canonical_group_id:
        group_ids.add(doc.canonical_group_id)

    if group_ids:
        group = db.get(CanonicalContentGroup, min(group_ids))
    else:
        feats = _document_features(db, document_id)
        slug_base = feats["slug"] or normalize_keyword(feats["title"])[:80] or f"doc-{document_id}"
        slug_base = re.sub(r"[^a-z0-9-]+", "-", slug_base).strip("-") or f"doc-{document_id}"
        group = CanonicalContentGroup(
            project_id=project_id,
            canonical_slug=slug_base,
            canonical_title=feats["title"] or slug_base,
            primary_topic=feats["topic_primary"] or None,
            strategy_status="open",
            duplicate_risk_level="medium",
            notes="Auto-suggested cluster (review required)",
        )
        db.add(group)
        db.flush()

    doc.canonical_group_id = group.id
    for pid in partner_ids:
        pdoc = db.get(ParsedDocument, pid)
        if pdoc:
            pdoc.canonical_group_id = group.id

    max_score = max(c["similarity_score"] for c in strong)
    if max_score >= 90:
        group.duplicate_risk_level = "critical"
    elif max_score >= settings.similarity_cannibalization_threshold:
        group.duplicate_risk_level = "high"
    else:
        group.duplicate_risk_level = "medium"

    for c in strong:
        link = upsert_similarity_link(db, project_id, c)
        link.canonical_group_id = group.id

    return group


def detect_cannibalization_warnings(db: Session, document_id: int) -> list[dict[str, Any]]:
    settings = get_settings()
    project_id = _resolve_project_id(db, document_id)
    if not project_id:
        return []

    links = db.scalars(
        select(DocumentSimilarityLink).where(
            DocumentSimilarityLink.project_id == project_id,
            (
                (DocumentSimilarityLink.document_id_a == document_id)
                | (DocumentSimilarityLink.document_id_b == document_id)
            ),
        )
    ).all()
    warnings: list[dict[str, Any]] = []
    state = _document_publish_state(db, document_id)

    for link in links:
        other_id = link.document_id_b if link.document_id_a == document_id else link.document_id_a
        other_state = _document_publish_state(db, other_id)
        if link.similarity_score < settings.similarity_cannibalization_threshold:
            continue
        if state == "published" and other_state == "published":
            warnings.append({
                "type": "seo_cannibalization",
                "document_id": other_id,
                "similarity_score": link.similarity_score,
                "similarity_type": link.similarity_type,
                "message": f"Published overlap with document #{other_id} (cannibalization risk)",
            })
        elif link.similarity_type in (SIMILARITY_NEAR_DUPLICATE, SIMILARITY_SAME_SOURCE):
            warnings.append({
                "type": "near_duplicate_published_cluster",
                "document_id": other_id,
                "similarity_score": link.similarity_score,
                "message": f"Near-duplicate cluster risk with document #{other_id}",
            })

    doc = db.get(ParsedDocument, document_id)
    if doc and doc.canonical_group_id:
        siblings = db.scalars(
            select(ParsedDocument).where(
                ParsedDocument.canonical_group_id == doc.canonical_group_id,
                ParsedDocument.id != document_id,
            )
        ).all()
        published_siblings = [s for s in siblings if _document_publish_state(db, s.id) == "published"]
        if state == "published" and len(published_siblings) >= 1:
            warnings.append({
                "type": "canonical_group_cannibalization",
                "canonical_group_id": doc.canonical_group_id,
                "published_siblings": [s.id for s in published_siblings],
                "message": "Multiple published documents in the same canonical group",
            })
    return warnings[:15]


def get_canonical_strategy_warnings(db: Session, document_id: int) -> list[str]:
    """Warnings for strategy/publish readiness — never blocks publish."""
    warnings: list[str] = []
    settings = get_settings()
    for item in detect_cannibalization_warnings(db, document_id):
        warnings.append(item.get("message") or item.get("type", "cannibalization"))

    links = db.scalars(
        select(DocumentSimilarityLink).where(
            (DocumentSimilarityLink.document_id_a == document_id)
            | (DocumentSimilarityLink.document_id_b == document_id)
        ).order_by(DocumentSimilarityLink.similarity_score.desc())
        .limit(10)
    ).all()
    for link in links:
        if link.similarity_score >= settings.similarity_near_duplicate_threshold:
            other = link.document_id_b if link.document_id_a == document_id else link.document_id_a
            warnings.append(
                f"Near-duplicate ({link.similarity_type}, score={link.similarity_score}) with #{other}"
            )
        if link.strategy_action and link.strategy_action != STRATEGY_PUBLISH_SAFE:
            warnings.append(f"Strategy suggestion: {link.strategy_action}")
    return list(dict.fromkeys(warnings))[:20]


def ensure_source_lineage(db: Session, document_id: int) -> RewriteLineage | None:
    project_id = _resolve_project_id(db, document_id)
    if not project_id:
        return None
    existing = db.scalar(
        select(RewriteLineage).where(
            RewriteLineage.derived_document_id == document_id,
            RewriteLineage.lineage_type == _LINEAGE_SOURCE,
        )
    )
    if existing:
        return existing
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        return None
    root_id = document_id
    url_norm = _normalize_url(doc.source_url or "")
    if url_norm:
        candidates = db.scalars(
            select(ParsedDocument)
            .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
            .where(ScrapingTask.project_id == project_id, ParsedDocument.id != document_id)
            .order_by(ParsedDocument.id.asc())
            .limit(300)
        ).all()
        for cand in candidates:
            if _normalize_url(cand.source_url or "") == url_norm:
                root_id = cand.id
                break

    row = RewriteLineage(
        project_id=project_id,
        root_source_document_id=root_id,
        derived_document_id=document_id,
        rewrite_generation=1,
        lineage_type=_LINEAGE_SOURCE,
    )
    db.add(row)
    db.flush()
    return row


def record_rewrite_lineage(db: Session, document_id: int) -> RewriteLineage | None:
    project_id = _resolve_project_id(db, document_id)
    if not project_id:
        return None
    root_row = ensure_source_lineage(db, document_id)
    root_id = root_row.root_source_document_id if root_row else document_id
    existing = db.scalar(
        select(RewriteLineage).where(
            RewriteLineage.derived_document_id == document_id,
            RewriteLineage.lineage_type == _LINEAGE_REWRITE,
        )
    )
    if existing:
        return existing
    gen = db.scalar(
        select(RewriteLineage.rewrite_generation)
        .where(RewriteLineage.root_source_document_id == root_id)
        .order_by(RewriteLineage.rewrite_generation.desc())
    )
    generation = (gen or 0) + 1
    row = RewriteLineage(
        project_id=project_id,
        root_source_document_id=root_id,
        derived_document_id=document_id,
        rewrite_generation=generation,
        lineage_type=_LINEAGE_REWRITE,
    )
    db.add(row)
    db.flush()
    return row


def record_revision_lineage(db: Session, document_id: int, revision_number: int) -> RewriteLineage | None:
    project_id = _resolve_project_id(db, document_id)
    if not project_id:
        return None
    existing = db.scalar(
        select(RewriteLineage).where(
            RewriteLineage.derived_document_id == document_id,
            RewriteLineage.lineage_type == _LINEAGE_REVISION,
            RewriteLineage.rewrite_generation == max(1, revision_number),
        )
    )
    if existing:
        return existing
    root_row = ensure_source_lineage(db, document_id)
    root_id = root_row.root_source_document_id if root_row else document_id
    row = RewriteLineage(
        project_id=project_id,
        root_source_document_id=root_id,
        derived_document_id=document_id,
        rewrite_generation=max(1, revision_number),
        lineage_type=_LINEAGE_REVISION,
    )
    db.add(row)
    db.flush()
    return row


def get_document_lineage(db: Session, document_id: int) -> dict[str, Any]:
    rows = db.scalars(
        select(RewriteLineage)
        .where(
            (RewriteLineage.derived_document_id == document_id)
            | (RewriteLineage.root_source_document_id == document_id)
        )
        .order_by(RewriteLineage.created_at.asc())
    ).all()
    revisions = db.scalars(
        select(DocumentRevision)
        .where(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.revision_number.asc())
    ).all()
    return {
        "document_id": document_id,
        "lineage_entries": [
            {
                "id": r.id,
                "root_source_document_id": r.root_source_document_id,
                "derived_document_id": r.derived_document_id,
                "rewrite_generation": r.rewrite_generation,
                "lineage_type": r.lineage_type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "revisions": [
            {
                "revision_number": rev.revision_number,
                "editorial_status": rev.editorial_status,
                "source_type": rev.source_type,
                "created_at": rev.created_at.isoformat() if rev.created_at else None,
            }
            for rev in revisions
        ],
    }


def get_document_similarity_summary(db: Session, document_id: int) -> dict[str, Any]:
    project_id = _resolve_project_id(db, document_id)
    doc = db.get(ParsedDocument, document_id)
    links = []
    if project_id:
        links = db.scalars(
            select(DocumentSimilarityLink)
            .where(
                DocumentSimilarityLink.project_id == project_id,
                (
                    (DocumentSimilarityLink.document_id_a == document_id)
                    | (DocumentSimilarityLink.document_id_b == document_id)
                ),
            )
            .order_by(DocumentSimilarityLink.similarity_score.desc())
            .limit(25)
        ).all()

    near_duplicates = []
    for link in links:
        if link.similarity_type in (SIMILARITY_NEAR_DUPLICATE, SIMILARITY_SAME_SOURCE, SIMILARITY_REWRITE_FAMILY):
            other = link.document_id_b if link.document_id_a == document_id else link.document_id_a
            near_duplicates.append({
                "document_id": other,
                "similarity_score": link.similarity_score,
                "similarity_type": link.similarity_type,
                "strategy_action": link.strategy_action,
            })

    group = None
    if doc and doc.canonical_group_id:
        g = db.get(CanonicalContentGroup, doc.canonical_group_id)
        if g:
            group = {
                "id": g.id,
                "canonical_slug": g.canonical_slug,
                "canonical_title": g.canonical_title,
                "duplicate_risk_level": g.duplicate_risk_level,
                "strategy_status": g.strategy_status,
            }

    return {
        "document_id": document_id,
        "canonical_group": group,
        "links": [
            {
                "id": l.id,
                "peer_document_id": l.document_id_b if l.document_id_a == document_id else l.document_id_a,
                "similarity_score": l.similarity_score,
                "similarity_type": l.similarity_type,
                "duplicate_risk": l.duplicate_risk,
                "strategy_action": l.strategy_action,
            }
            for l in links
        ],
        "near_duplicates": near_duplicates,
        "cannibalization_warnings": detect_cannibalization_warnings(db, document_id),
        "strategy_warnings": get_canonical_strategy_warnings(db, document_id),
    }


def analyze_document_similarity(
    db: Session,
    document_id: int,
    *,
    persist: bool = True,
    deep: bool = False,
) -> dict[str, Any]:
    project_id = _resolve_project_id(db, document_id)
    if not project_id:
        raise ValueError("Document has no project context")

    limit = 400 if deep else 80
    candidates = _candidate_document_ids(db, project_id=project_id, document_id=document_id, limit=limit)
    settings = get_settings()
    comparisons: list[dict[str, Any]] = []
    persisted_links: list[int] = []

    for other_id in candidates:
        try:
            cmp = compare_document_pair(db, document_id, other_id)
        except ValueError:
            continue
        if cmp["similarity_score"] < max(40, settings.similarity_topic_overlap_threshold - 15):
            continue
        comparisons.append(cmp)
        if persist:
            link = upsert_similarity_link(db, project_id, cmp)
            persisted_links.append(link.id)

    comparisons.sort(key=lambda x: x["similarity_score"], reverse=True)
    group = None
    if persist and comparisons:
        group = suggest_canonical_group(db, project_id=project_id, document_id=document_id, comparisons=comparisons)
        ensure_source_lineage(db, document_id)
        doc = db.get(ParsedDocument, document_id)
        if doc and doc.rewritten_text:
            record_rewrite_lineage(db, document_id)

    return {
        "document_id": document_id,
        "project_id": project_id,
        "analyzed_pairs": len(candidates),
        "matches": len(comparisons),
        "top_matches": comparisons[:15],
        "persisted_link_ids": persisted_links,
        "canonical_group_id": group.id if group else (db.get(ParsedDocument, document_id).canonical_group_id if db.get(ParsedDocument, document_id) else None),
        "deep": deep,
    }


def quick_similarity_check(db: Session, document_id: int) -> dict[str, Any]:
    """Lightweight sync check — same URL + title collision only."""
    project_id = _resolve_project_id(db, document_id)
    if not project_id:
        return {"skipped": True}
    feats = _document_features(db, document_id)
    hits = 0
    if feats["source_url_norm"]:
        same_url = db.scalars(
            select(ParsedDocument.id)
            .join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id)
            .where(
                ScrapingTask.project_id == project_id,
                ParsedDocument.id != document_id,
            )
            .limit(50)
        ).all()
        for oid in same_url:
            of = _document_features(db, oid)
            if of["source_url_norm"] == feats["source_url_norm"]:
                cmp = compare_document_pair(db, document_id, oid)
                upsert_similarity_link(db, project_id, cmp)
                hits += 1
    return {"document_id": document_id, "quick_hits": hits}
