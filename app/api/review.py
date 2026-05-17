from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parsed_document import ParsedDocument
from app.services.review_service import run_review_for_document

router = APIRouter(prefix="/api/documents", tags=["review"])


@router.post("/{document_id}/run-review")
def api_run_review(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document.clean_text:
        raise HTTPException(status_code=400, detail="No clean_text to review")

    try:
        result = run_review_for_document(db, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": result.success,
        "skipped": result.skipped,
        "take": result.take,
        "score": result.score,
        "reason": result.reason,
        "review_result_id": result.review_result_id,
        "llm_run_id": result.llm_run_id,
        "model_alias": result.model_alias,
        "content_type": result.content_type,
        "recommended_angle": result.recommended_angle,
        "risks": result.risks,
        "error_message": result.error_message,
    }
