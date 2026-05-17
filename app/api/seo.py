from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parsed_document import ParsedDocument
from app.services.seo_service import run_seo_for_document

router = APIRouter(prefix="/api/documents", tags=["seo"])


@router.post("/{document_id}/run-seo")
def api_run_seo(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document.rewritten_text and not document.clean_text:
        raise HTTPException(status_code=400, detail="No content for SEO enrichment")

    try:
        result = run_seo_for_document(db, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": result.success,
        "skipped": result.skipped,
        "seo_metadata_id": result.seo_metadata_id,
        "seo_title": result.seo_title,
        "slug": result.slug,
        "llm_run_id": result.llm_run_id,
        "model_alias": result.model_alias,
        "error_message": result.error_message,
        "warnings": result.warnings,
    }
