from sqlalchemy.orm import Session

from app.llm.models import CompletionResult
from app.models.llm_run import LLMRun


def record_llm_run(
    db: Session,
    *,
    model_alias: str,
    upstream_model: str,
    success: bool,
    task_id: int | None = None,
    project_id: int | None = None,
    prompt_template: str | None = None,
    result: CompletionResult | None = None,
    error_message: str | None = None,
) -> LLMRun:
    run = LLMRun(
        task_id=task_id,
        project_id=project_id,
        model_alias=model_alias,
        upstream_model=upstream_model,
        prompt_template=prompt_template,
        input_tokens=result.input_tokens if result else None,
        output_tokens=result.output_tokens if result else None,
        latency_ms=result.latency_ms if result else None,
        finish_reason=result.finish_reason if result else None,
        fallback_used=result.fallback_used if result else False,
        success=success,
        error_message=error_message,
    )
    db.add(run)
    db.flush()
    return run
