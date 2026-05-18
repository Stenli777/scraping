"""Canonical content group queries for admin and API."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.canonical_content_group import CanonicalContentGroup
from app.models.document_similarity_link import DocumentSimilarityLink
from app.models.parsed_document import ParsedDocument
from app.models.rewrite_lineage import RewriteLineage
from app.services.document_similarity_service import get_document_lineage, get_document_similarity_summary


def list_canonical_groups(
    db: Session,
    *,
    project_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    q = select(CanonicalContentGroup).order_by(CanonicalContentGroup.id.desc()).limit(limit)
    if project_id:
        q = q.where(CanonicalContentGroup.project_id == project_id)
    groups = db.scalars(q).all()
    out = []
    for g in groups:
        doc_count = db.scalar(
            select(func.count()).select_from(ParsedDocument).where(ParsedDocument.canonical_group_id == g.id)
        )
        out.append({
            "id": g.id,
            "project_id": g.project_id,
            "canonical_slug": g.canonical_slug,
            "canonical_title": g.canonical_title,
            "primary_topic": g.primary_topic,
            "strategy_status": g.strategy_status,
            "duplicate_risk_level": g.duplicate_risk_level,
            "document_count": doc_count or 0,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        })
    return out


def get_canonical_group_detail(db: Session, group_id: int) -> dict[str, Any]:
    group = db.get(CanonicalContentGroup, group_id)
    if not group:
        raise ValueError(f"Canonical group {group_id} not found")

    documents = db.scalars(
        select(ParsedDocument).where(ParsedDocument.canonical_group_id == group_id).order_by(ParsedDocument.id.asc())
    ).all()
    doc_ids = [d.id for d in documents]

    links: list[DocumentSimilarityLink] = []
    if doc_ids:
        links = list(
            db.scalars(
                select(DocumentSimilarityLink)
                .where(
                    DocumentSimilarityLink.canonical_group_id == group_id,
                )
                .order_by(DocumentSimilarityLink.similarity_score.desc())
                .limit(50)
            ).all()
        )

    lineages = []
    if doc_ids:
        lineages = list(
            db.scalars(
                select(RewriteLineage).where(
                    RewriteLineage.root_source_document_id.in_(doc_ids)
                    | RewriteLineage.derived_document_id.in_(doc_ids)
                )
            ).all()
        )

    strategy_warnings: list[str] = []
    for did in doc_ids[:10]:
        summary = get_document_similarity_summary(db, did)
        strategy_warnings.extend(summary.get("strategy_warnings") or [])

    campaign_overlap = [
        l for l in links if l.similarity_type == "campaign_overlap"
    ]

    return {
        "group": {
            "id": group.id,
            "project_id": group.project_id,
            "canonical_slug": group.canonical_slug,
            "canonical_title": group.canonical_title,
            "primary_topic": group.primary_topic,
            "strategy_status": group.strategy_status,
            "duplicate_risk_level": group.duplicate_risk_level,
            "notes": group.notes,
        },
        "documents": [{"id": d.id, "source_url": d.source_url} for d in documents],
        "similarity_links": [
            {
                "id": l.id,
                "document_id_a": l.document_id_a,
                "document_id_b": l.document_id_b,
                "similarity_score": l.similarity_score,
                "similarity_type": l.similarity_type,
                "strategy_action": l.strategy_action,
            }
            for l in links
        ],
        "lineage": [
            {
                "id": ln.id,
                "root_source_document_id": ln.root_source_document_id,
                "derived_document_id": ln.derived_document_id,
                "lineage_type": ln.lineage_type,
                "rewrite_generation": ln.rewrite_generation,
            }
            for ln in lineages
        ],
        "strategy_warnings": list(dict.fromkeys(strategy_warnings))[:20],
        "campaign_overlap_count": len(campaign_overlap),
        "similarity_graph_summary": {
            "link_count": len(links),
            "max_score": max((l.similarity_score for l in links), default=0),
            "high_risk_links": sum(1 for l in links if l.duplicate_risk in ("high", "critical")),
        },
    }
