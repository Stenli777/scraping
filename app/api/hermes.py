"""Hermes optional orchestration API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_hermes_enabled
from app.db.session import get_db
from app.hermes.health import check_hermes_health
from app.hermes.routing import list_hermes_aliases
from app.models.hermes_run import HermesRun
from app.models.parsed_document import ParsedDocument
from app.services.hermes_service import run_research_summary, run_rewrite_critique

router = APIRouter(tags=["hermes"])


class HermesAgentBody(BaseModel):
    agent: str | None = None


@router.get("/api/hermes/health")
def api_hermes_health():
    if not is_hermes_enabled():
        return {
            "enabled": False,
            "available": False,
            "status": "disabled",
            "aliases": list_hermes_aliases(),
        }
    h = check_hermes_health()
    return {
        "enabled": True,
        "available": h.available,
        "status": h.status,
        "latency_ms": h.latency_ms,
        "service": h.service,
        "version": h.version,
        "detail": h.detail,
        "aliases": list_hermes_aliases(),
    }


@router.get("/api/hermes/runs")
def api_hermes_runs(
    document_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = select(HermesRun).order_by(HermesRun.id.desc()).limit(min(limit, 200))
    if document_id is not None:
        q = q.where(HermesRun.document_id == document_id)
    runs = db.scalars(q).all()
    return {
        "runs": [
            {
                "id": r.id,
                "task_kind": r.task_kind,
                "document_id": r.document_id,
                "project_id": r.project_id,
                "success": r.success,
                "fallback_used": r.fallback_used,
                "agent_requested": r.agent_requested,
                "agent_used": r.agent_used,
                "model_used": r.model_used,
                "latency_ms": r.latency_ms,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ]
    }


@router.post("/api/documents/{document_id}/hermes/research")
def api_hermes_research(
    document_id: int,
    body: HermesAgentBody | None = None,
    db: Session = Depends(get_db),
):
    if not is_hermes_enabled():
        raise HTTPException(status_code=503, detail="Hermes disabled (ENABLE_HERMES=false)")
    if not db.get(ParsedDocument, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    result = run_research_summary(
        db, document_id, agent=body.agent if body else None
    )
    if not result.success and not result.hermes_run_id:
        raise HTTPException(status_code=503, detail=result.error_message or "Hermes failed")
    status_code = 200 if result.success else 502
    return {
        "success": result.success,
        "hermes_run_id": result.hermes_run_id,
        "result": result.result,
        "warnings": result.warnings,
        "errors": result.errors,
        "agent_used": result.agent_used,
        "model_used": result.model_used,
        "fallback_used": result.fallback_used,
    }


@router.post("/api/documents/{document_id}/hermes/critique")
def api_hermes_critique(
    document_id: int,
    body: HermesAgentBody | None = None,
    db: Session = Depends(get_db),
):
    if not is_hermes_enabled():
        raise HTTPException(status_code=503, detail="Hermes disabled (ENABLE_HERMES=false)")
    if not db.get(ParsedDocument, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        result = run_rewrite_critique(
            db, document_id, agent=body.agent if body else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result.success and not result.hermes_run_id:
        raise HTTPException(status_code=503, detail=result.error_message or "Hermes failed")
    return {
        "success": result.success,
        "hermes_run_id": result.hermes_run_id,
        "result": result.result,
        "warnings": result.warnings,
        "errors": result.errors,
        "agent_used": result.agent_used,
        "model_used": result.model_used,
        "fallback_used": result.fallback_used,
    }
