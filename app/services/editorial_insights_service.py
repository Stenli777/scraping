"""Simple editorial analytics — no LLM."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_performance import ContentPerformance
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.seo_metadata import SeoMetadata


def top_performing_content(db: Session, *, project_id: int | None = None, limit: int = 10) -> list[dict]:
    q = select(ContentPerformance).order_by(ContentPerformance.performance_score.desc().nullslast())
    if project_id:
        q = q.where(ContentPerformance.project_id == project_id)
    rows = db.scalars(q.limit(limit)).all()
    return [_perf_row(db, p) for p in rows if p.performance_score is not None]


def low_performing_content(db: Session, *, project_id: int | None = None, limit: int = 10) -> list[dict]:
    q = select(ContentPerformance).order_by(ContentPerformance.performance_score.asc().nullsfirst())
    if project_id:
        q = q.where(ContentPerformance.project_id == project_id)
    rows = db.scalars(q.limit(limit)).all()
    return [_perf_row(db, p) for p in rows]


def high_quality_low_traffic(db: Session, *, project_id: int | None = None, limit: int = 10) -> list[dict]:
    from app.models.content_quality_score import ContentQualityScore

    q = (
        select(ContentPerformance)
        .where(ContentPerformance.latest_views.isnot(None))
        .where(ContentPerformance.latest_views < 500)
        .order_by(ContentPerformance.performance_score.asc())
    )
    if project_id:
        q = q.where(ContentPerformance.project_id == project_id)
    results = []
    for perf in db.scalars(q.limit(limit * 3)).all():
        quality = db.scalar(
            select(ContentQualityScore)
            .where(ContentQualityScore.document_id == perf.document_id)
            .order_by(ContentQualityScore.id.desc())
        )
        if quality and quality.overall_score and quality.overall_score >= 70:
            results.append(_perf_row(db, perf))
        if len(results) >= limit:
            break
    return results


def low_quality_high_traffic(db: Session, *, project_id: int | None = None, limit: int = 10) -> list[dict]:
    from app.models.content_quality_score import ContentQualityScore

    q = (
        select(ContentPerformance)
        .where(ContentPerformance.latest_views.isnot(None))
        .where(ContentPerformance.latest_views >= 1000)
        .order_by(ContentPerformance.latest_views.desc())
    )
    if project_id:
        q = q.where(ContentPerformance.project_id == project_id)
    results = []
    for perf in db.scalars(q.limit(limit * 3)).all():
        quality = db.scalar(
            select(ContentQualityScore)
            .where(ContentQualityScore.document_id == perf.document_id)
            .order_by(ContentQualityScore.id.desc())
        )
        if quality and quality.overall_score is not None and quality.overall_score < 60:
            results.append(_perf_row(db, perf))
        if len(results) >= limit:
            break
    return results


def best_tags_categories(db: Session, *, project_id: int | None = None, limit: int = 10) -> list[dict]:
    perfs = top_performing_content(db, project_id=project_id, limit=50)
    tag_scores: dict[str, list[int]] = {}
    cat_scores: dict[str, list[int]] = {}
    for row in perfs:
        seo = db.scalar(
            select(SeoMetadata)
            .where(SeoMetadata.document_id == row["document_id"])
            .order_by(SeoMetadata.id.desc())
        )
        score = row.get("performance_score") or 0
        if seo:
            for tag in seo.tags_json or []:
                tag_scores.setdefault(str(tag), []).append(score)
            if seo.suggested_category:
                cat_scores.setdefault(seo.suggested_category, []).append(score)
    tags = [
        {"tag": k, "avg_score": round(sum(v) / len(v), 1), "count": len(v)}
        for k, v in sorted(tag_scores.items(), key=lambda x: -sum(x[1]) / len(x[1]))[:limit]
    ]
    categories = [
        {"category": k, "avg_score": round(sum(v) / len(v), 1), "count": len(v)}
        for k, v in sorted(cat_scores.items(), key=lambda x: -sum(x[1]) / len(x[1]))[:limit]
    ]
    return {"tags": tags, "categories": categories}


def content_aging_signals(db: Session, *, days_stale: int = 30, limit: int = 20) -> list[dict]:
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_stale)
    q = (
        select(PublicationRecord)
        .where(PublicationRecord.published_at.isnot(None))
        .where(PublicationRecord.published_at < cutoff)
        .order_by(PublicationRecord.published_at.asc())
    )
    records = db.scalars(q.limit(limit)).all()
    out = []
    for rec in records:
        perf = db.scalar(
            select(ContentPerformance).where(
                ContentPerformance.publication_record_id == rec.id
            )
        )
        out.append({
            "publication_record_id": rec.id,
            "document_id": rec.document_id,
            "published_at": rec.published_at.isoformat() if rec.published_at else None,
            "external_url": rec.external_url,
            "trend": perf.trend if perf else "unknown",
            "performance_score": perf.performance_score if perf else None,
        })
    return out


def _perf_row(db: Session, perf: ContentPerformance) -> dict:
    rec = db.get(PublicationRecord, perf.publication_record_id)
    return {
        "document_id": perf.document_id,
        "publication_record_id": perf.publication_record_id,
        "revision_id": rec.revision_id if rec else None,
        "performance_score": perf.performance_score,
        "latest_views": perf.latest_views,
        "latest_ctr": perf.latest_ctr,
        "trend": perf.trend,
        "status": perf.status,
        "external_url": rec.external_url if rec else None,
    }
