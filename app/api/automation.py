"""Automation and scheduler API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_automation_enabled, is_scheduler_enabled
from app.db.session import get_db
from app.models.automation_run import AutomationRun
from app.models.automation_rule import AutomationRule
from app.scheduler.heartbeat import get_heartbeat_status
from app.scheduler.rules import next_run_preview
from app.services.automation_service import AutomationError, execute_automation_rule, set_rule_enabled

router = APIRouter(tags=["automation"])


def _require_automation():
    if not is_automation_enabled():
        raise HTTPException(status_code=503, detail="Automation disabled")


@router.get("/api/automation/rules")
def list_rules(db: Session = Depends(get_db)):
    if not is_automation_enabled():
        raise HTTPException(status_code=503, detail="Automation disabled")
    rules = db.scalars(select(AutomationRule).order_by(AutomationRule.id.asc())).all()
    return {
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
            }
            for r in rules
        ]
    }


@router.post("/api/automation/rules/{rule_id}/run")
def manual_run(rule_id: int, db: Session = Depends(get_db)):
    _require_automation()
    try:
        run = execute_automation_rule(db, rule_id, trigger="manual")
    except AutomationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "success": run.status == "completed",
        "run_id": run.id,
        "status": run.status,
        "created_discoveries": run.created_discoveries,
        "created_tasks": run.created_tasks,
        "error_message": run.error_message,
    }


@router.post("/api/automation/rules/{rule_id}/enable")
def enable_rule(rule_id: int, db: Session = Depends(get_db)):
    _require_automation()
    try:
        rule = set_rule_enabled(db, rule_id, True)
    except AutomationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": rule.id, "enabled": rule.enabled}


@router.post("/api/automation/rules/{rule_id}/disable")
def disable_rule(rule_id: int, db: Session = Depends(get_db)):
    _require_automation()
    try:
        rule = set_rule_enabled(db, rule_id, False)
    except AutomationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": rule.id, "enabled": rule.enabled}


@router.get("/api/automation/runs")
def list_runs(rule_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    if not is_automation_enabled():
        raise HTTPException(status_code=503, detail="Automation disabled")
    q = select(AutomationRun).order_by(AutomationRun.id.desc()).limit(min(limit, 200))
    if rule_id:
        q = q.where(AutomationRun.automation_rule_id == rule_id)
    runs = db.scalars(q).all()
    return {
        "runs": [
            {
                "id": r.id,
                "automation_rule_id": r.automation_rule_id,
                "status": r.status,
                "created_tasks": r.created_tasks,
                "created_discoveries": r.created_discoveries,
                "created_documents": r.created_documents,
                "error_message": r.error_message,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ]
    }


@router.get("/api/scheduler/status")
def scheduler_status(db: Session = Depends(get_db)):
    hb = get_heartbeat_status(db)
    return {
        "scheduler_enabled": is_scheduler_enabled(),
        "automation_enabled": is_automation_enabled(),
        "heartbeat": hb,
    }
