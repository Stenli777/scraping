"""Persist Hermes orchestration audit records."""

from sqlalchemy.orm import Session

from app.hermes.schemas import HermesTaskRequest, HermesTaskResponse
from app.models.hermes_run import HermesRun


def record_hermes_run(
    db: Session,
    *,
    request: HermesTaskRequest,
    response: HermesTaskResponse,
    project_id: int | None = None,
    document_id: int | None = None,
    error_message: str | None = None,
) -> HermesRun:
    run = HermesRun(
        task_kind=request.task_kind,
        project_id=project_id,
        document_id=document_id,
        request_payload_json={
            "task_kind": request.task_kind,
            "agent": request.agent,
            "payload": request.payload,
            "metadata": request.metadata,
        },
        response_payload_json={
            "success": response.success,
            "result": response.result,
            "warnings": response.warnings,
            "errors": response.errors,
            "raw": response.raw,
        },
        agent_requested=request.agent,
        agent_used=response.agent_used,
        model_used=response.model_used,
        success=response.success,
        fallback_used=response.fallback_used,
        latency_ms=response.latency_ms,
        error_message=error_message
        or ("; ".join(response.errors) if response.errors else None),
    )
    db.add(run)
    db.flush()
    return run
