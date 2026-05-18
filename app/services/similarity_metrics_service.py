"""Health metrics for canonical similarity layer."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document_similarity_link import DocumentSimilarityLink
from app.models.llm_enrichment_job import EnrichmentJobStatus, EnrichmentType, LlmEnrichmentJob


def get_similarity_health(db: Session) -> dict:
    pending = db.scalar(
        select(func.count())
        .select_from(LlmEnrichmentJob)
        .where(
            LlmEnrichmentJob.enrichment_type == EnrichmentType.SIMILARITY_ANALYSIS,
            LlmEnrichmentJob.status.in_([EnrichmentJobStatus.QUEUED, EnrichmentJobStatus.RUNNING]),
        )
    ) or 0
    high_risk = db.scalar(
        select(func.count())
        .select_from(DocumentSimilarityLink)
        .where(DocumentSimilarityLink.duplicate_risk.in_(["high", "critical"]))
    ) or 0
    status = "ok"
    if pending > 50:
        status = "degraded"
    return {
        "status": status,
        "pending_analysis": pending,
        "high_risk_duplicates": high_risk,
    }
