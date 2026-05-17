"""Content quality review API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.content_quality_score import ContentQualityScore
from app.models.parsed_document import ParsedDocument
from app.services.quality_service import run_quality_for_document

router = APIRouter(prefix="/api/documents", tags=["quality"])


@router.post("/{document_id}/run-quality")
def api_run_quality(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        result = run_quality_for_document(db, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.skipped:
        raise HTTPException(status_code=503, detail=result.error_message or "Quality review disabled")

    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=result.error_message or "Quality review failed",
        )

    return {
        "success": True,
        "quality_score_id": result.quality_score_id,
        "llm_run_id": result.llm_run_id,
        "overall_score": result.overall_score,
        "verdict": result.verdict,
        "risks": result.risks,
        "recommendations": result.recommendations,
        "metadata": result.metadata,
    }


@router.get("/{document_id}/quality-scores")
def api_list_quality_scores(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    scores = db.scalars(
        select(ContentQualityScore)
        .where(ContentQualityScore.document_id == document_id)
        .order_by(ContentQualityScore.id.desc())
        .limit(50)
    ).all()

    return {
        "document_id": document_id,
        "scores": [
            {
                "id": s.id,
                "overall_score": s.overall_score,
                "readability_score": s.readability_score,
                "seo_score": s.seo_score,
                "factual_consistency_score": s.factual_consistency_score,
                "structure_score": s.structure_score,
                "usefulness_score": s.usefulness_score,
                "spamminess_score": s.spamminess_score,
                "verdict": s.verdict,
                "risks": s.risks_json,
                "recommendations": s.recommendations_json,
                "llm_run_id": s.llm_run_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in scores
        ],
    }
