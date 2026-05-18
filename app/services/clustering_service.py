"""Topic clustering ? deterministic heuristics, no vector DB."""

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_cluster_link import DocumentClusterLink
from app.models.parsed_document import ParsedDocument
from app.models.seo_metadata import SeoMetadata
from app.models.topic_cluster import CLUSTER_TYPES, TopicCluster

STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "how", "what", "why", "???", "???", "???", "???",
        "???", "???", "???", "???", "???", "???", "???", "???", "???", "??", "??", "??",
    }
)

SEARCH_INTENTS = frozenset({"commercial", "informational", "transactional", "navigational"})


def normalize_keyword(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[^\w\s\-]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(text: str) -> set[str]:
    return {t for t in normalize_keyword(text).split() if t and t not in STOPWORDS and len(t) > 2}


def slugify(name: str) -> str:
    s = normalize_keyword(name).replace(" ", "-")
    return re.sub(r"-+", "-", s)[:120] or "cluster"


def infer_search_intent(keywords: list[str], cluster_type: str | None = None) -> str:
    if cluster_type == "commercial":
        return "commercial"
    joined = " ".join(keywords).lower()
    if any(w in joined for w in ("buy", "price", "??????", "????", "?????", "????????")):
        return "commercial"
    if any(w in joined for w in ("vs", "compare", "?????????", "??????")):
        return "commercial"
    if any(w in joined for w in ("how", "guide", "???", "????", "??????????")):
        return "informational"
    return "informational"


def extract_topics_for_document(
    db: Session,
    document_id: int,
    *,
    persist_audit: bool = True,
) -> dict[str, Any]:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")

    seo = db.scalar(
        select(SeoMetadata)
        .where(SeoMetadata.document_id == document_id)
        .order_by(SeoMetadata.id.desc())
    )
    meta = document.metadata_json or {}
    title = (
        (seo.h1 if seo else None)
        or (seo.seo_title if seo else None)
        or meta.get("extracted_title")
        or meta.get("title")
        or ""
    )
    tags = list((seo.tags_json if seo else None) or [])
    text_sample = (document.rewritten_text or document.clean_text or "")[:2000]

    tokens = tokenize(title) | tokenize(text_sample)
    for tag in tags:
        tokens |= tokenize(str(tag))

    keywords = sorted(tokens, key=len, reverse=True)[:12]
    primary = keywords[0] if keywords else normalize_keyword(title)[:80] or "general topic"
    secondary = [k for k in keywords[1:6] if k != primary]

    # title-based primary topic (human readable)
    primary_topic = title.strip() or primary.replace("-", " ").title()

    search_intent = infer_search_intent([primary] + secondary + tags)

    result = {
        "primary_topic": primary_topic,
        "secondary_topics": secondary,
        "keywords": keywords[:10],
        "search_intent": search_intent,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }

    if persist_audit:
        meta = dict(document.metadata_json or {})
        audits = list(meta.get("topic_extractions") or [])
        audits.append(result)
        meta["topic_extractions"] = audits[-20:]
        meta["topics"] = result
        document.metadata_json = meta
        db.flush()

    return result


def cluster_similarity(
    *,
    keywords_a: set[str],
    keywords_b: set[str],
    slug_a: str = "",
    slug_b: str = "",
) -> float:
    if not keywords_a or not keywords_b:
        return SequenceMatcher(None, slug_a, slug_b).ratio()
    inter = len(keywords_a & keywords_b)
    union = len(keywords_a | keywords_b) or 1
    jaccard = inter / union
    slug_sim = SequenceMatcher(None, slug_a, slug_b).ratio()
    return round(0.6 * jaccard + 0.4 * slug_sim, 3)


def suggest_cluster(
    db: Session,
    *,
    project_id: int,
    document_id: int | None = None,
    primary_keyword: str | None = None,
    cluster_type: str = "informational",
) -> dict[str, Any]:
    if document_id:
        topics = extract_topics_for_document(db, document_id, persist_audit=False)
        primary_keyword = primary_keyword or topics["keywords"][0] if topics.get("keywords") else topics["primary_topic"]
        search_intent = topics.get("search_intent")
    else:
        topics = None
        search_intent = infer_search_intent([primary_keyword or ""], cluster_type)

    pk = normalize_keyword(primary_keyword or "topic")
    clusters = db.scalars(
        select(TopicCluster).where(TopicCluster.project_id == project_id).order_by(TopicCluster.priority.desc())
    ).all()

    best: TopicCluster | None = None
    best_score = 0.0
    pk_tokens = tokenize(pk)
    for cluster in clusters:
        ck = tokenize(cluster.primary_keyword or "") | tokenize(cluster.name)
        sec = {normalize_keyword(k) for k in (cluster.secondary_keywords_json or [])}
        score = cluster_similarity(
            keywords_a=pk_tokens,
            keywords_b=ck | sec,
            slug_a=slugify(pk),
            slug_b=cluster.slug,
        )
        if score > best_score:
            best_score = score
            best = cluster

    suggested_name = pk.replace("-", " ").title() if pk else "New cluster"
    return {
        "suggested_cluster_id": best.id if best and best_score >= 0.35 else None,
        "similarity_score": best_score,
        "suggested_name": suggested_name,
        "suggested_slug": slugify(suggested_name),
        "suggested_cluster_type": cluster_type if cluster_type in CLUSTER_TYPES else "informational",
        "suggested_primary_keyword": pk,
        "suggested_search_intent": search_intent,
        "topics": topics,
    }


def assign_document_to_cluster(
    db: Session,
    *,
    document_id: int,
    cluster_id: int,
    is_primary: bool = True,
    assigned_by: str | None = "operator",
) -> DocumentClusterLink:
    existing = db.scalar(
        select(DocumentClusterLink).where(
            DocumentClusterLink.document_id == document_id,
            DocumentClusterLink.cluster_id == cluster_id,
        )
    )
    if existing:
        existing.is_primary = is_primary
        return existing

    if is_primary:
        db.query(DocumentClusterLink).filter(
            DocumentClusterLink.document_id == document_id,
            DocumentClusterLink.is_primary.is_(True),
        ).update({"is_primary": False})

    link = DocumentClusterLink(
        document_id=document_id,
        cluster_id=cluster_id,
        is_primary=is_primary,
        assigned_by=assigned_by,
    )
    db.add(link)
    db.flush()
    return link
