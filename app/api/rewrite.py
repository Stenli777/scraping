from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parsed_document import ParsedDocument
from app.services.rewrite_service import rerun_rewrite_for_document

router = APIRouter(prefix="/api/documents", tags=["rewrite"])


@router.post("/{document_id}/rerun-rewrite")
def api_rerun_rewrite(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document.clean_text:
        raise HTTPException(status_code=400, detail="No clean_text to rewrite")

    try:
        result = rerun_rewrite_for_document(db, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.refresh(document)
    return {
        "success": result.success,
        "document_id": document_id,
        "rewritten_text_length": len(document.rewritten_text or ""),
        "provider": result.provider,
        "model_alias": result.model_alias,
        "upstream_model": result.upstream_model,
        "fallback_used": result.fallback_used,
        "llm_run_id": result.llm_run_id,
        "error_message": result.error_message,
        "warnings": result.warnings,
    }
