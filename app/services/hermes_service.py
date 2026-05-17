"""Optional Hermes orchestration — isolated from Scrap pipeline."""

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.feature_flags import is_hermes_enabled
from app.hermes.adapters import (
    build_campaign_payload,
    build_critique_payload,
    build_research_payload,
)
from app.hermes.client import HermesClient
from app.hermes.exceptions import HermesDisabledError, HermesError
from app.hermes.schemas import HermesTaskRequest
from app.models.hermes_run import HermesRun
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.services.hermes_run_service import record_hermes_run
from app.services.project_profile_service import build_review_context, resolve_task_project
from app.services.quality_service import get_latest_quality_score
from app.services.revision_service import get_latest_revision
from app.services.publish_service import _latest_seo

logger = logging.getLogger(__name__)


@dataclass
class HermesOrchestrationResult:
    success: bool
    hermes_run_id: int | None = None
    task_kind: str = ""
    result: Any = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    agent_used: str | None = None
    model_used: str | None = None
    fallback_used: bool = False
    error_message: str | None = None


def _run_task(
    db: Session,
    request: HermesTaskRequest,
    *,
    project_id: int | None,
    document_id: int | None,
) -> HermesOrchestrationResult:
    if not is_hermes_enabled():
        return HermesOrchestrationResult(
            success=False,
            task_kind=request.task_kind,
            error_message="Hermes disabled (ENABLE_HERMES=false)",
        )

    client = HermesClient()
    try:
        response = client.run_task(request)
        run = record_hermes_run(
            db,
            request=request,
            response=response,
            project_id=project_id,
            document_id=document_id,
        )
        db.commit()
        return HermesOrchestrationResult(
            success=response.success,
            hermes_run_id=run.id,
            task_kind=request.task_kind,
            result=response.result,
            warnings=response.warnings,
            errors=response.errors,
            agent_used=response.agent_used,
            model_used=response.model_used,
            fallback_used=response.fallback_used,
            error_message="; ".join(response.errors) if response.errors else None,
        )
    except HermesDisabledError as exc:
        return HermesOrchestrationResult(
            success=False,
            task_kind=request.task_kind,
            error_message=str(exc),
        )
    except HermesError as exc:
        logger.warning("Hermes task failed kind=%s: %s", request.task_kind, exc)
        from app.hermes.schemas import HermesTaskResponse

        fail_resp = HermesTaskResponse(
            success=False,
            errors=[str(exc)],
            agent_used=request.agent,
        )
        run = record_hermes_run(
            db,
            request=request,
            response=fail_resp,
            project_id=project_id,
            document_id=document_id,
            error_message=str(exc),
        )
        db.commit()
        return HermesOrchestrationResult(
            success=False,
            hermes_run_id=run.id,
            task_kind=request.task_kind,
            error_message=str(exc),
        )


def run_research_summary(
    db: Session,
    document_id: int,
    *,
    agent: str | None = None,
) -> HermesOrchestrationResult:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")

    task = document.task
    project = resolve_task_project(db, task) if task else None
    seo = _latest_seo(db, document_id)
    seo_snap = None
    if seo:
        seo_snap = {
            "seo_title": seo.seo_title,
            "slug": seo.slug,
        }

    payload = build_research_payload(
        source_url=document.source_url or "",
        title=(document.metadata_json or {}).get("title", ""),
        clean_text=document.clean_text or "",
        rewritten_text=document.rewritten_text,
        seo_snapshot=seo_snap,
        profile_context=build_review_context(project) if project else None,
    )

    settings = get_settings()
    request = HermesTaskRequest(
        task_kind="research_summary",
        agent=agent or settings.hermes_default_agent,
        payload=payload,
        metadata={"document_id": document_id},
    )
    return _run_task(
        db,
        request,
        project_id=project.id if project else None,
        document_id=document_id,
    )


def run_rewrite_critique(
    db: Session,
    document_id: int,
    *,
    agent: str | None = None,
) -> HermesOrchestrationResult:
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")
    if not document.rewritten_text:
        raise ValueError("Document has no rewritten_text for critique")

    task = document.task
    project = resolve_task_project(db, task) if task else None
    seo = _latest_seo(db, document_id)
    quality = get_latest_quality_score(db, document_id)
    rev = get_latest_revision(db, document_id)

    seo_snap = rev.seo_snapshot_json if rev else None
    if seo and not seo_snap:
        seo_snap = {"seo_title": seo.seo_title, "slug": seo.slug}
    quality_snap = rev.quality_snapshot_json if rev else None
    if quality and not quality_snap:
        quality_snap = {
            "overall_score": quality.overall_score,
            "verdict": quality.verdict,
        }

    payload = build_critique_payload(
        source_url=document.source_url or "",
        rewritten_text=document.rewritten_text,
        seo_snapshot=seo_snap,
        quality_snapshot=quality_snap,
        profile_context=build_review_context(project) if project else None,
    )

    settings = get_settings()
    request = HermesTaskRequest(
        task_kind="rewrite_critique",
        agent=agent or settings.hermes_default_agent,
        payload=payload,
        metadata={"document_id": document_id},
    )
    return _run_task(
        db,
        request,
        project_id=project.id if project else None,
        document_id=document_id,
    )


def run_campaign_ideas(
    db: Session,
    project_id: int,
    *,
    agent: str | None = None,
    topics: list[str] | None = None,
) -> HermesOrchestrationResult:
    project = db.get(Project, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    profile = build_review_context(project)
    payload = build_campaign_payload(
        project_slug=project.slug,
        profile_context=profile,
        topics=topics,
    )

    settings = get_settings()
    request = HermesTaskRequest(
        task_kind="campaign_ideas",
        agent=agent or settings.hermes_default_agent,
        payload=payload,
        metadata={"project_id": project_id},
    )
    return _run_task(db, request, project_id=project_id, document_id=None)


def get_latest_hermes_result(db: Session, document_id: int, task_kind: str) -> HermesRun | None:
    from sqlalchemy import select

    return db.scalar(
        select(HermesRun)
        .where(HermesRun.document_id == document_id, HermesRun.task_kind == task_kind)
        .order_by(HermesRun.id.desc())
    )
