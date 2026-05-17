"""Automation and scheduler API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_automation_enabled, is_scheduler_enabled
from app.db.session import get_db
from app.models.automation_run import AutomationRun
from app.models.automation_rule import AutomationRule
from app.scheduler.rules import next_run_preview
from app.scheduler.status import build_scheduler_status
from app.services.automation_service import (
    AutomationError,
    cancel_automation_run,
    enqueue_automation_run,
    get_rule_rate_usage,
    mark_run_failed,
    set_rule_enabled,
)

router = APIRouter(tags=["automation"])


def _run_dict(r: AutomationRun) -> dict:
    return {
        "id": r.id,
        "automation_rule_id": r.automation_rule_id,
        "status": r.status,
        "trigger_type": r.trigger_type,
        "requested_by": r.requested_by,
        "progress": r.progress_json,
        "created_tasks": r.created_tasks,
        "created_discoveries": r.created_discoveries,
        "created_documents": r.created_documents,
        "error_message": r.error_message,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "heartbeat_at": r.heartbeat_at.isoformat() if r.heartbeat_at else None,
    }


@router.get("/api/automation/rules")
def list_rules(db: Session = Depends(get_db)):
    rules = db.scalars(select(AutomationRule).order_by(AutomationRule.id.asc())).all()
    return {
        "scheduler_enabled": is_scheduler_enabled(),
        "automation_enabled": is_automation_enabled(),
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "enabled": r.enabled,
                "trigger_type": r.trigger_type,
                "schedule_cron": r.schedule_cron,
                "automation_type": r.automation_type,
                "rate_limit_per_hour": r.rate_limit_per_hour,
                "max_daily_runs": r.max_daily_runs,
                "next_run_preview": next_run_preview(r, db),
                "rate_usage": get_rule_rate_usage(db, r),
            }
            for r in rules
        ],
    }


@router.post("/api/automation/rules/{rule_id}/run")
def manual_run(rule_id: int, db: Session = Depends(get_db)):
    """Enqueue run — returns immediately (non-blocking)."""
    try:
        run = enqueue_automation_run(db, rule_id, trigger="manual", requested_by="api")
    except AutomationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "automation_run_id": run.id,
        "status": run.status,
    }


@router.post("/api/automation/rules/{rule_id}/enable")
def enable_rule(rule_id: int, db: Session = Depends(get_db)):
    if not is_automation_enabled():
        raise HTTPException(status_code=503, detail="Automation disabled")
    try:
        rule = set_rule_enabled(db, rule_id, True)
    except AutomationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": rule.id, "enabled": rule.enabled}


@router.post("/api/automation/rules/{rule_id}/disable")
def disable_rule(rule_id: int, db: Session = Depends(get_db)):
    if not is_automation_enabled():
        raise HTTPException(status_code=503, detail="Automation disabled")
    try:
        rule = set_rule_enabled(db, rule_id, False)
    except AutomationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": rule.id, "enabled": rule.enabled}


@router.get("/api/automation/runs")
def list_runs(rule_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    q = select(AutomationRun).order_by(AutomationRun.id.desc()).limit(min(limit, 200))
    if rule_id:
        q = q.where(AutomationRun.automation_rule_id == rule_id)
    runs = db.scalars(q).all()
    return {"runs": [_run_dict(r) for r in runs]}


@router.get("/api/automation/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AutomationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    data = _run_dict(run)
    data["logs"] = run.logs_json
    data["affected_entities"] = run.affected_entities_json
    return data


@router.post("/api/automation/runs/{run_id}/cancel")
def cancel_run(run_id: int, db: Session = Depends(get_db)):
    try:
        run = cancel_automation_run(db, run_id)
    except AutomationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": run.id, "status": run.status}


@router.post("/api/automation/runs/{run_id}/mark-failed")
def api_mark_failed(run_id: int, db: Session = Depends(get_db)):
    try:
        run = mark_run_failed(db, run_id)
    except AutomationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": run.id, "status": run.status, "error_message": run.error_message}


@router.get("/api/scheduler/status")
def scheduler_status(db: Session = Depends(get_db)):
    return build_scheduler_status(db)
