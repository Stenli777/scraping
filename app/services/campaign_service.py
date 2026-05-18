"""Campaign planning, coverage, duplicates, suggestions."""

from __future__ import annotations

from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import PublishRunStatus
from app.models.campaign_document_link import CampaignDocumentLink
from app.models.content_campaign import CAMPAIGN_STATUSES, ContentCampaign
from app.models.content_performance import ContentPerformance
from app.models.document_cluster_link import DocumentClusterLink
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.publish_run import PublishRun
from app.models.scraping_task import ScrapingTask
from app.models.seo_metadata import SeoMetadata
from app.models.topic_cluster import CLUSTER_TYPES, TopicCluster
from app.services.clustering_service import normalize_keyword, slugify, tokenize
from app.services.strategy_gate_service import filter_strategy_document_ids
from app.services.strategy_topics_service import get_effective_strategy_topics, topics_eligible_for_campaign_intelligence

DUPLICATE_TITLE_THRESHOLD = 0.82
DUPLICATE_SLUG_THRESHOLD = 0.88
DUPLICATE_KEYWORD_OVERLAP = 0.55


def create_campaign(
    db: Session,
    *,
    project_id: int,
    name: str,
    slug: str | None = None,
    description: str | None = None,
    campaign_status: str = "draft",
    target_keywords: list[str] | None = None,
    target_audience: str | None = None,
    content_goal: str | None = None,
    publishing_goal: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ContentCampaign:
    if campaign_status not in CAMPAIGN_STATUSES:
        raise ValueError(f"Invalid campaign_status: {campaign_status}")
    slug_val = slug or slugify(name)
    campaign = ContentCampaign(
        project_id=project_id,
        name=name,
        slug=slug_val,
        description=description,
        campaign_status=campaign_status,
        target_keywords_json=target_keywords or [],
        target_audience=target_audience,
        content_goal=content_goal,
        publishing_goal=publishing_goal,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(campaign)
    db.flush()
    return campaign


def create_cluster(
    db: Session,
    *,
    project_id: int,
    name: str,
    slug: str | None = None,
    cluster_type: str = "informational",
    primary_keyword: str | None = None,
    secondary_keywords: list[str] | None = None,
    search_intent: str | None = None,
    priority: int = 50,
    notes: str | None = None,
) -> TopicCluster:
    if cluster_type not in CLUSTER_TYPES:
        raise ValueError(f"Invalid cluster_type: {cluster_type}")
    cluster = TopicCluster(
        project_id=project_id,
        name=name,
        slug=slug or slugify(name),
        cluster_type=cluster_type,
        primary_keyword=primary_keyword or normalize_keyword(name),
        secondary_keywords_json=secondary_keywords or [],
        search_intent=search_intent,
        priority=priority,
        notes=notes,
    )
    db.add(cluster)
    db.flush()
    return cluster


def assign_document_to_campaign(
    db: Session,
    *,
    document_id: int,
    campaign_id: int,
    link_role: str = "planned",
) -> CampaignDocumentLink:
    existing = db.scalar(
        select(CampaignDocumentLink).where(
            CampaignDocumentLink.document_id == document_id,
            CampaignDocumentLink.campaign_id == campaign_id,
        )
    )
    if existing:
        existing.link_role = link_role
        return existing
    link = CampaignDocumentLink(
        document_id=document_id,
        campaign_id=campaign_id,
        link_role=link_role,
    )
    db.add(link)
    db.flush()
    return link


def _document_title_slug(db: Session, document_id: int) -> tuple[str, str, set[str]]:
    doc = db.get(ParsedDocument, document_id)
    if not doc:
        return "", "", set()
    seo = db.scalar(
        select(SeoMetadata).where(SeoMetadata.document_id == document_id).order_by(SeoMetadata.id.desc())
    )
    meta = doc.metadata_json or {}
    title = (seo.h1 if seo else None) or (seo.seo_title if seo else None) or meta.get("title") or ""
    slug = (seo.slug if seo else None) or ""
    topics = (meta.get("topics") or {}).get("keywords") or []
    tags = (seo.tags_json if seo else None) or []
    kw = tokenize(title) | tokenize(slug) | {normalize_keyword(k) for k in topics + tags}
    return title, slug, kw


def detect_duplicate_topics(
    db: Session,
    *,
    document_id: int,
    project_id: int | None = None,
) -> list[dict[str, Any]]:
    """Warnings only ? does not block pipeline."""
    title, slug, keywords = _document_title_slug(db, document_id)
    if not title and not slug:
        return []

    doc = db.get(ParsedDocument, document_id)
    task = doc.task if doc else None
    if project_id is None and task:
        from app.services.project_profile_service import resolve_task_project
        project = resolve_task_project(db, task)
        project_id = project.id if project else None

    q = select(ParsedDocument).where(ParsedDocument.id != document_id)
    if project_id:
        q = q.join(ScrapingTask, ParsedDocument.task_id == ScrapingTask.id).where(
            ScrapingTask.project_id == project_id
        )
    others = db.scalars(q.limit(200)).all()

    warnings: list[dict[str, Any]] = []
    norm_title = normalize_keyword(title)
    for other in others:
        o_title, o_slug, o_kw = _document_title_slug(db, other.id)
        if not o_title:
            continue
        title_sim = SequenceMatcher(None, norm_title, normalize_keyword(o_title)).ratio()
        slug_sim = SequenceMatcher(None, slug or "", o_slug or "").ratio() if slug or o_slug else 0.0
        if keywords and o_kw:
            overlap = len(keywords & o_kw) / max(len(keywords | o_kw), 1)
        else:
            overlap = 0.0

        if title_sim >= DUPLICATE_TITLE_THRESHOLD:
            warnings.append({
                "type": "similar_title",
                "document_id": other.id,
                "score": round(title_sim, 3),
                "message": f"Similar title to document #{other.id}",
            })
        elif slug_sim >= DUPLICATE_SLUG_THRESHOLD:
            warnings.append({
                "type": "similar_slug",
                "document_id": other.id,
                "score": round(slug_sim, 3),
                "message": f"Similar slug to document #{other.id}",
            })
        elif overlap >= DUPLICATE_KEYWORD_OVERLAP:
            warnings.append({
                "type": "keyword_overlap",
                "document_id": other.id,
                "score": round(overlap, 3),
                "message": f"Keyword overlap with document #{other.id}",
            })
    return warnings[:10]


def _document_publish_state(db: Session, document_id: int) -> str:
    pub = db.scalar(
        select(PublicationRecord)
        .where(PublicationRecord.document_id == document_id)
        .order_by(PublicationRecord.id.desc())
    )
    if pub and pub.publication_status == "draft" and pub.external_article_id:
        return "published"
    run = db.scalar(
        select(PublishRun)
        .where(
            PublishRun.document_id == document_id,
            PublishRun.status == PublishRunStatus.SUCCESS.value,
            PublishRun.dry_run.is_(False),
        )
        .order_by(PublishRun.id.desc())
    )
    if run:
        return "published"
    run_draft = db.scalar(
        select(PublishRun)
        .where(PublishRun.document_id == document_id, PublishRun.status == PublishRunStatus.DRY_RUN.value)
        .order_by(PublishRun.id.desc())
    )
    if run_draft:
        return "draft"
    return "in_progress"


def cluster_coverage(
    db: Session,
    cluster_id: int,
    *,
    include_blocked: bool = False,
) -> dict[str, Any]:
    cluster = db.get(TopicCluster, cluster_id)
    if not cluster:
        raise ValueError(f"Cluster {cluster_id} not found")

    links = db.scalars(
        select(DocumentClusterLink).where(DocumentClusterLink.cluster_id == cluster_id)
    ).all()
    doc_ids_all = [lnk.document_id for lnk in links]
    doc_ids, excluded_count, excluded_docs = filter_strategy_document_ids(
        db, doc_ids_all, include_blocked=include_blocked
    )
    published = drafts = in_progress = 0
    covered_keywords: set[str] = set()

    for did in doc_ids:
        state = _document_publish_state(db, did)
        if state == "published":
            published += 1
        elif state == "draft":
            drafts += 1
        else:
            in_progress += 1
        _, _, kw = _document_title_slug(db, did)
        covered_keywords |= kw

    target_keywords = {normalize_keyword(cluster.primary_keyword or "")} | {
        normalize_keyword(k) for k in (cluster.secondary_keywords_json or [])
    }
    target_keywords.discard("")
    missing = sorted(k for k in target_keywords if k and k not in covered_keywords)

    # human-readable gaps from secondary keywords not covered
    missing_content = []
    for kw in cluster.secondary_keywords_json or []:
        nk = normalize_keyword(str(kw))
        if nk and nk not in covered_keywords:
            missing_content.append(str(kw))

    return {
        "cluster": cluster.name,
        "cluster_id": cluster.id,
        "documents": len(doc_ids),
        "published": published,
        "drafts": drafts,
        "in_progress": in_progress,
        "missing_content": missing_content[:15],
        "missing_keywords": missing[:15],
        "document_ids": doc_ids,
        "document_ids_all": doc_ids_all,
        "excluded_strategy_count": excluded_count,
        "excluded_strategy_documents": excluded_docs,
        "include_blocked": include_blocked,
    }


def campaign_coverage(
    db: Session,
    campaign_id: int,
    *,
    include_blocked: bool = False,
) -> dict[str, Any]:
    campaign = db.get(ContentCampaign, campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    links = db.scalars(
        select(CampaignDocumentLink).where(CampaignDocumentLink.campaign_id == campaign_id)
    ).all()
    doc_ids_all = [lnk.document_id for lnk in links]
    doc_ids, excluded_count, excluded_docs = filter_strategy_document_ids(
        db, doc_ids_all, include_blocked=include_blocked
    )

    published = drafts = planned = 0
    cluster_ids: set[int] = set()
    for did in doc_ids:
        state = _document_publish_state(db, did)
        if state == "published":
            published += 1
        elif state == "draft":
            drafts += 1
        else:
            planned += 1
        cl = db.scalars(
            select(DocumentClusterLink.cluster_id).where(DocumentClusterLink.document_id == did)
        ).all()
        cluster_ids.update(cl)

    clusters_summary = []
    for cid in cluster_ids:
        try:
            clusters_summary.append(cluster_coverage(db, cid))
        except ValueError:
            pass

    target_kw = [normalize_keyword(k) for k in (campaign.target_keywords_json or [])]
    covered = set()
    for did in doc_ids:
        _, _, kw = _document_title_slug(db, did)
        covered |= kw
    missing_topics = [k for k in target_kw if k and k not in covered]

    duplicate_warnings = []
    for did in doc_ids[:20]:
        duplicate_warnings.extend(detect_duplicate_topics(db, document_id=did, project_id=campaign.project_id))

    return {
        "campaign_id": campaign.id,
        "campaign": campaign.name,
        "status": campaign.campaign_status,
        "documents": len(doc_ids),
        "published": published,
        "drafts": drafts,
        "planned": planned,
        "clusters": clusters_summary,
        "missing_topics": missing_topics,
        "duplicate_warnings": duplicate_warnings[:15],
        "document_ids": doc_ids,
        "document_ids_all": doc_ids_all,
        "excluded_strategy_count": excluded_count,
        "excluded_strategy_documents": excluded_docs,
        "include_blocked": include_blocked,
    }


def suggested_articles_for_campaign(db: Session, campaign_id: int) -> list[dict[str, Any]]:
    coverage = campaign_coverage(db, campaign_id)
    suggestions: list[dict[str, Any]] = []

    for topic in coverage.get("missing_topics", [])[:8]:
        title = topic.replace("-", " ").title()
        suggestions.append({"title": title, "reason": "uncovered campaign keyword"})

    for cluster_block in coverage.get("clusters", []):
        for gap in cluster_block.get("missing_content", [])[:5]:
            suggestions.append({"title": str(gap), "reason": "cluster gap"})

    campaign = db.get(ContentCampaign, campaign_id)
    if campaign:
        try:
            weak = cluster_performance_summary(db, project_id=campaign.project_id).get("underperforming", [])
        except Exception:
            weak = []
        for item in weak[:3]:
            suggestions.append({
                "title": f"Refresh content for cluster: {item.get('cluster')}",
                "reason": "underperforming cluster",
            })

    # dedupe by title
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for s in suggestions:
        key = normalize_keyword(s["title"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique[:15]


def cluster_performance_summary(db: Session, *, project_id: int) -> dict[str, Any]:
    clusters = db.scalars(
        select(TopicCluster).where(TopicCluster.project_id == project_id)
    ).all()
    rows: list[dict[str, Any]] = []

    for cluster in clusters:
        links = db.scalars(
            select(DocumentClusterLink).where(DocumentClusterLink.cluster_id == cluster.id)
        ).all()
        scores: list[int] = []
        views = 0
        for link in links:
            perf = db.scalar(
                select(ContentPerformance)
                .join(PublicationRecord, ContentPerformance.publication_record_id == PublicationRecord.id)
                .where(PublicationRecord.document_id == link.document_id)
            )
            if perf and perf.performance_score is not None:
                scores.append(int(perf.performance_score))
            if perf and perf.latest_views:
                views += int(perf.latest_views)

        avg_score = round(sum(scores) / len(scores)) if scores else None
        rows.append({
            "cluster_id": cluster.id,
            "cluster": cluster.name,
            "documents": len(links),
            "avg_performance_score": avg_score,
            "total_views": views,
        })

    ranked = sorted(
        [r for r in rows if r["avg_performance_score"] is not None],
        key=lambda x: x["avg_performance_score"] or 0,
        reverse=True,
    )
    top = ranked[:5]
    under = sorted(
        [r for r in rows if r["documents"] > 0 and (r["avg_performance_score"] or 0) < 50],
        key=lambda x: x["avg_performance_score"] or 0,
    )[:5]

    return {
        "clusters": rows,
        "top_performing": top,
        "underperforming": under,
    }


def campaign_performance_summary(db: Session, campaign_id: int) -> dict[str, Any]:
    campaign = db.get(ContentCampaign, campaign_id)
    if not campaign:
        raise ValueError(f"Campaign not found")
    coverage = campaign_coverage(db, campaign_id)
    cluster_perf = cluster_performance_summary(db, project_id=campaign.project_id)
    return {
        "campaign_id": campaign_id,
        "campaign": campaign.name,
        "coverage": coverage,
        "cluster_performance": cluster_perf,
    }


def document_strategy_context(db: Session, document_id: int) -> dict[str, Any]:
    clusters = db.scalars(
        select(TopicCluster)
        .join(DocumentClusterLink, DocumentClusterLink.cluster_id == TopicCluster.id)
        .where(DocumentClusterLink.document_id == document_id)
    ).all()
    campaigns = db.scalars(
        select(ContentCampaign)
        .join(CampaignDocumentLink, CampaignDocumentLink.campaign_id == ContentCampaign.id)
        .where(CampaignDocumentLink.document_id == document_id)
    ).all()
    doc = db.get(ParsedDocument, document_id)
    project_id = None
    if doc and doc.task:
        from app.services.project_profile_service import resolve_task_project
        project = resolve_task_project(db, doc.task)
        project_id = project.id if project else None

    warnings = detect_duplicate_topics(db, document_id=document_id, project_id=project_id)
    topics_meta = (doc.metadata_json or {}).get("topics") if doc else {}
    strategy_blocked = topics_meta.get("strategy_allowed") is False if topics_meta else False
    if strategy_blocked:
        enriched = []
        for w in warnings:
            if isinstance(w, dict):
                enriched.append({**w, "strategy_ignored": True})
            else:
                enriched.append(w)
        warnings = enriched
    suggested = None
    if project_id:
        from app.services.clustering_service import suggest_cluster
        try:
            suggested = suggest_cluster(db, project_id=project_id, document_id=document_id)
        except Exception:
            suggested = None
    coverage_blocks = [cluster_coverage(db, c.id) for c in clusters]

    strategy_readiness = None
    strategy_blocked_message = None
    if doc:
        from app.services.strategy_gate_service import get_strategy_readiness
        from app.services.enrichment_service import enrichment_history, latest_enrichment_for_document, job_to_dict
        strategy_readiness = get_strategy_readiness(db, document_id)
        topics = (doc.metadata_json or {}).get("topics") or {}
        if topics.get("strategy_allowed") is False:
            strategy_blocked_message = (
                "This document is blocked from strategy calculations."
            )

    return {
        "clusters": [{"id": c.id, "name": c.name, "slug": c.slug, "cluster_type": c.cluster_type} for c in clusters],
        "campaigns": [{"id": c.id, "name": c.name, "slug": c.slug, "status": c.campaign_status} for c in campaigns],
        "duplicate_warnings": warnings,
        "coverage_context": coverage_blocks,
        "topics": (doc.metadata_json or {}).get("topics") if doc else None,
        "suggested_cluster": suggested,
        "strategy_readiness": strategy_readiness,
        "strategy_blocked_message": strategy_blocked_message,
        "latest_enrichment_job": job_to_dict(latest_enrichment_for_document(db, document_id)) if doc else None,
        "enrichment_history": [job_to_dict(j) for j in enrichment_history(db, document_id)] if doc else [],
    }
