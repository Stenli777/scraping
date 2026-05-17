from sqlalchemy.orm import Session

from app.core.pipeline_states import PipelineStage, assert_transition
from app.models.pipeline_event import PipelineEvent


def emit_pipeline_event(
    db: Session,
    task_id: int,
    stage: PipelineStage | str,
    status: str,
    payload: dict | None = None,
    *,
    validate_transition: bool = False,
    current_stage: PipelineStage | None = None,
) -> PipelineEvent:
    stage_value = stage.value if isinstance(stage, PipelineStage) else stage
    if validate_transition and current_stage is not None:
        assert_transition(current_stage, PipelineStage(stage_value))

    event = PipelineEvent(
        task_id=task_id,
        stage=stage_value,
        status=status,
        payload_json=payload,
    )
    db.add(event)
    db.flush()
    return event


def map_legacy_task_status_to_stage(status: str) -> str:
    """Map existing scraping_tasks.status to pipeline_events.stage."""
    mapping = {
        "queued": PipelineStage.QUEUED.value,
        "fetching": PipelineStage.FETCHING.value,
        "parsing": PipelineStage.PARSING.value,
        "cleaning": PipelineStage.CLEANING.value,
        "reviewing": PipelineStage.REVIEW_PENDING.value,
        "rewriting": PipelineStage.REWRITING.value,
        "seo_enriching": PipelineStage.SEO_ENRICH_PENDING.value,
        "saving": PipelineStage.PUBLISHING.value,
        "done": PipelineStage.PUBLISHED_DRAFT.value,
        "failed_retryable": PipelineStage.FAILED_RETRYABLE.value,
        "error": PipelineStage.FAILED_RETRYABLE.value,
    }
    return mapping.get(status, status)
