"""LLM enrichment jobs API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.llm_enrichment_job import LlmEnrichmentJob
from app.services.enrichment_service import (
    cancel_enrichment_job,
    job_to_dict,
    replay_enrichment_job,
    retry_enrichment_job,
)
from app.services.enrichment_metrics_service import get_enrichment_metrics

router = APIRouter(prefix="/api/enrichment-jobs", tags=["enrichment-jobs"])


@router.get("/metrics")
def enrichment_metrics(db: Session = Depends(get_db)):
    return get_enrichment_metrics(db)


@router.get("")
def list_enrichment_jobs(
    status: str | None = None,
    document_id: int | None = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = select(LlmEnrichmentJob).order_by(LlmEnrichmentJob.id.desc()).limit(limit)
    if status:
        q = q.where(LlmEnrichmentJob.status == status)
    if document_id:
        q = q.where(LlmEnrichmentJob.document_id == document_id)
    jobs = db.scalars(q).all()
    return {"items": [job_to_dict(j) for j in jobs]}


@router.get("/{job_id}")
def get_enrichment_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(LlmEnrichmentJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_dict(job)


@router.post("/{job_id}/retry")
def api_retry_enrichment_job(job_id: int, db: Session = Depends(get_db)):
    try:
        job = retry_enrichment_job(db, job_id)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job_to_dict(job)


@router.post("/{job_id}/cancel")
def api_cancel_enrichment_job(job_id: int, db: Session = Depends(get_db)):
    try:
        job = cancel_enrichment_job(db, job_id)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job_to_dict(job)



@router.post("/{job_id}/replay")
def api_replay_enrichment_job(job_id: int, db: Session = Depends(get_db)):
    try:
        job = replay_enrichment_job(db, job_id)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job_to_dict(job)
