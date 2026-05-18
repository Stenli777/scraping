"""Campaign planning and topic cluster API."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.content_campaign import ContentCampaign
from app.models.topic_cluster import TopicCluster
from app.services.campaign_service import (
    assign_document_to_campaign,
    campaign_coverage,
    campaign_performance_summary,
    cluster_coverage,
    cluster_performance_summary,
    create_campaign,
    create_cluster,
    suggested_articles_for_campaign,
)
from app.services.clustering_service import assign_document_to_cluster, suggest_cluster

router = APIRouter(tags=["campaigns"])


class CampaignCreateBody(BaseModel):
    project_id: int
    name: str
    slug: str | None = None
    description: str | None = None
    campaign_status: str = "draft"
    target_keywords: list[str] = Field(default_factory=list)
    target_audience: str | None = None
    content_goal: str | None = None
    publishing_goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ClusterCreateBody(BaseModel):
    project_id: int
    name: str
    slug: str | None = None
    cluster_type: str = "informational"
    primary_keyword: str | None = None
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str | None = None
    priority: int = 50
    notes: str | None = None


class AssignClusterBody(BaseModel):
    cluster_id: int
    is_primary: bool = True


class AssignCampaignBody(BaseModel):
    campaign_id: int
    link_role: str = "planned"


def _serialize_campaign(c: ContentCampaign) -> dict:
    return {
        "id": c.id,
        "project_id": c.project_id,
        "name": c.name,
        "slug": c.slug,
        "description": c.description,
        "campaign_status": c.campaign_status,
        "target_keywords": c.target_keywords_json or [],
        "target_audience": c.target_audience,
        "content_goal": c.content_goal,
        "publishing_goal": c.publishing_goal,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _serialize_cluster(c: TopicCluster) -> dict:
    return {
        "id": c.id,
        "project_id": c.project_id,
        "name": c.name,
        "slug": c.slug,
        "cluster_type": c.cluster_type,
        "primary_keyword": c.primary_keyword,
        "secondary_keywords": c.secondary_keywords_json or [],
        "search_intent": c.search_intent,
        "priority": c.priority,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/api/campaigns")
def list_campaigns(project_id: int | None = None, db: Session = Depends(get_db)):
    q = select(ContentCampaign).order_by(ContentCampaign.id.desc())
    if project_id is not None:
        q = q.where(ContentCampaign.project_id == project_id)
    items = db.scalars(q.limit(100)).all()
    return {"campaigns": [_serialize_campaign(c) for c in items]}


@router.post("/api/campaigns")
def post_campaign(body: CampaignCreateBody, db: Session = Depends(get_db)):
    try:
        campaign = create_campaign(
            db,
            project_id=body.project_id,
            name=body.name,
            slug=body.slug,
            description=body.description,
            campaign_status=body.campaign_status,
            target_keywords=body.target_keywords,
            target_audience=body.target_audience,
            content_goal=body.content_goal,
            publishing_goal=body.publishing_goal,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_campaign(campaign)


@router.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(ContentCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _serialize_campaign(campaign)


@router.get("/api/campaigns/{campaign_id}/coverage")
def get_campaign_coverage(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return campaign_coverage(db, campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/campaigns/{campaign_id}/suggested-articles")
def get_suggested_articles(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(ContentCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"suggestions": suggested_articles_for_campaign(db, campaign_id)}


@router.get("/api/campaigns/{campaign_id}/performance")
def get_campaign_performance(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return campaign_performance_summary(db, campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/clusters")
def list_clusters(project_id: int | None = None, db: Session = Depends(get_db)):
    q = select(TopicCluster).order_by(TopicCluster.priority.desc(), TopicCluster.id.desc())
    if project_id is not None:
        q = q.where(TopicCluster.project_id == project_id)
    items = db.scalars(q.limit(100)).all()
    return {"clusters": [_serialize_cluster(c) for c in items]}


@router.get("/api/clusters/suggest")
def api_suggest_cluster(
    project_id: int,
    document_id: int | None = None,
    primary_keyword: str | None = None,
    db: Session = Depends(get_db),
):
    return suggest_cluster(db, project_id=project_id, document_id=document_id, primary_keyword=primary_keyword)


@router.post("/api/clusters")
def post_cluster(body: ClusterCreateBody, db: Session = Depends(get_db)):
    try:
        cluster = create_cluster(
            db,
            project_id=body.project_id,
            name=body.name,
            slug=body.slug,
            cluster_type=body.cluster_type,
            primary_keyword=body.primary_keyword,
            secondary_keywords=body.secondary_keywords,
            search_intent=body.search_intent,
            priority=body.priority,
            notes=body.notes,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_cluster(cluster)


@router.get("/api/clusters/{cluster_id}")
def get_cluster(cluster_id: int, db: Session = Depends(get_db)):
    cluster = db.get(TopicCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    perf = cluster_performance_summary(db, project_id=cluster.project_id)
    cluster_row = next((r for r in perf["clusters"] if r["cluster_id"] == cluster_id), None)
    return {
        **_serialize_cluster(cluster),
        "coverage": cluster_coverage(db, cluster_id),
        "performance": cluster_row,
    }


@router.get("/api/clusters/{cluster_id}/coverage")
def get_cluster_coverage(cluster_id: int, db: Session = Depends(get_db)):
    try:
        return cluster_coverage(db, cluster_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/projects/{project_id}/cluster-performance")
def api_cluster_performance(project_id: int, db: Session = Depends(get_db)):
    return cluster_performance_summary(db, project_id=project_id)
