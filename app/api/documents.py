from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.exporters.json_markdown import document_to_json, document_to_markdown
from app.models.parsed_document import ParsedDocument
from app.schemas.documents import DocumentRead
from app.services.publish_readiness_service import get_publish_readiness

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/{document_id}", response_model=DocumentRead)
def api_get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/publish-readiness")
def api_publish_readiness(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return get_publish_readiness(db, document_id)


@router.get("/{document_id}/export/json")
def api_export_json(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(
        content=document_to_json(document),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="document_{document_id}.json"'},
    )


@router.get("/{document_id}/export/markdown")
def api_export_markdown(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return PlainTextResponse(
        content=document_to_markdown(document),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="document_{document_id}.md"'},
    )

from app.services.campaign_service import (
    assign_document_to_campaign,
    detect_duplicate_topics,
    document_strategy_context,
)
from app.services.clustering_service import assign_document_to_cluster, extract_topics_for_document


class AssignClusterRequest(BaseModel):
    cluster_id: int
    is_primary: bool = True


class AssignCampaignRequest(BaseModel):
    campaign_id: int
    link_role: str = "planned"


class ExtractTopicsRequest(BaseModel):
    use_llm_cleanup: bool | None = None


@router.post("/{document_id}/extract-topics")
def api_extract_topics(
    document_id: int,
    body: ExtractTopicsRequest | None = None,
    db: Session = Depends(get_db),
):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        use_llm = body.use_llm_cleanup if body else None
        result = extract_topics_for_document(
            db,
            document_id,
            persist_audit=True,
            use_llm_cleanup=use_llm,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/{document_id}/strategy-readiness")
def api_strategy_readiness(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    from app.services.strategy_gate_service import get_strategy_readiness

    return get_strategy_readiness(db, document_id)


@router.post("/{document_id}/assign-cluster")
def api_assign_cluster(
    document_id: int,
    body: AssignClusterRequest,
    db: Session = Depends(get_db),
):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    link = assign_document_to_cluster(
        db,
        document_id=document_id,
        cluster_id=body.cluster_id,
        is_primary=body.is_primary,
    )
    db.commit()
    return {"document_id": document_id, "cluster_id": body.cluster_id, "link_id": link.id}


@router.post("/{document_id}/assign-campaign")
def api_assign_campaign(
    document_id: int,
    body: AssignCampaignRequest,
    db: Session = Depends(get_db),
):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    link = assign_document_to_campaign(
        db,
        document_id=document_id,
        campaign_id=body.campaign_id,
        link_role=body.link_role,
    )
    db.commit()
    return {"document_id": document_id, "campaign_id": body.campaign_id, "link_id": link.id}


@router.get("/{document_id}/strategy")
def api_document_strategy(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_strategy_context(db, document_id)


@router.get("/{document_id}/similarity")
def api_document_similarity(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    from app.services.document_similarity_service import get_document_similarity_summary

    return get_document_similarity_summary(db, document_id)


@router.get("/{document_id}/lineage")
def api_document_lineage(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    from app.services.document_similarity_service import get_document_lineage

    return get_document_lineage(db, document_id)


@router.post("/{document_id}/analyze-similarity")
def api_analyze_similarity(
    document_id: int,
    deep: bool = False,
    queue_async: bool = False,
    db: Session = Depends(get_db),
):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    from app.services.document_similarity_service import analyze_document_similarity, quick_similarity_check
    from app.services.enrichment_service import queue_similarity_analysis_job
    from app.services.project_profile_service import resolve_task_project

    quick = quick_similarity_check(db, document_id)
    if queue_async and not deep:
        project = resolve_task_project(db, document.task) if document.task else None
        job = queue_similarity_analysis_job(db, document_id=document_id, project_id=project.id if project else None)
        db.commit()
        return {"queued": True, "job_id": job.id if job else None, "quick": quick}
    result = analyze_document_similarity(db, document_id, persist=True, deep=deep)
    if not deep:
        project = resolve_task_project(db, document.task) if document.task else None
        queue_similarity_analysis_job(db, document_id=document_id, project_id=project.id if project else None)
    db.commit()
    return {"quick": quick, "analysis": result}


@router.get("/{document_id}/duplicate-warnings")
def api_duplicate_warnings(document_id: int, db: Session = Depends(get_db)):
    document = db.get(ParsedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"warnings": detect_duplicate_topics(db, document_id=document_id)}
