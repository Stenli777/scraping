"""Admin routes for analytics-ready queue and manual metrics import."""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.feature_flags import all_flags
from app.db.session import get_db
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.publication_record import PublicationRecord
from app.services.analytics_ready_service import (
    build_analytics_dashboard,
    list_analytics_ready_publications,
)
from app.services.analytics_service import AnalyticsValidationError, create_snapshot
from app.services.publication_confirmation_service import (
    analytics_ready,
    get_publication_confirmation_status,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/admin/analytics-ready", response_class=HTMLResponse)
def admin_analytics_ready(request: Request, db: Session = Depends(get_db)):
    if not all_flags().get("ENABLE_ANALYTICS"):
        return RedirectResponse("/admin", status_code=302)
    rows = list_analytics_ready_publications(db)
    return templates.TemplateResponse(
        request,
        "analytics_ready.html",
        {
            "request": request,
            "rows": rows,
            "title": "Analytics ready",
            "feature_flags": all_flags(),
        },
    )


@router.get("/admin/publications/{publication_id}/analytics/import", response_class=HTMLResponse)
def admin_analytics_import_form(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    if not all_flags().get("ENABLE_ANALYTICS"):
        return RedirectResponse("/admin", status_code=302)
    pub = db.get(PublicationRecord, publication_id)
    if not pub:
        return RedirectResponse("/admin/publications", status_code=302)
    status = get_publication_confirmation_status(db, publication_id)
    return templates.TemplateResponse(
        request,
        "analytics_import.html",
        {
            "request": request,
            "pub": pub,
            "status": status,
            "ready": analytics_ready(pub),
            "errors": [],
            "form": {},
            "title": f"Import metrics — publication #{publication_id}",
            "feature_flags": all_flags(),
        },
    )


@router.post("/admin/publications/{publication_id}/analytics/import")
def admin_analytics_import_submit(
    publication_id: int,
    request: Request,
    db: Session = Depends(get_db),
    snapshot_date: str = Form(""),
    views: str = Form(""),
    unique_visitors: str = Form(""),
    avg_time_seconds: str = Form(""),
    bounce_rate: str = Form(""),
    ctr: str = Form(""),
    impressions: str = Form(""),
    conversions: str = Form(""),
    position_avg: str = Form(""),
    source: str = Form("manual"),
    import_notes: str = Form(""),
    imported_by: str = Form("operator"),
):
    if not all_flags().get("ENABLE_ANALYTICS"):
        return RedirectResponse("/admin", status_code=302)
    pub = db.get(PublicationRecord, publication_id)
    if not pub:
        return RedirectResponse("/admin/publications", status_code=302)

    form = {
        "snapshot_date": snapshot_date,
        "views": views,
        "unique_visitors": unique_visitors,
        "avg_time_seconds": avg_time_seconds,
        "bounce_rate": bounce_rate,
        "ctr": ctr,
        "impressions": impressions,
        "conversions": conversions,
        "position_avg": position_avg,
        "source": source,
        "import_notes": import_notes,
        "imported_by": imported_by,
    }

    def _parse_int(v: str) -> int | None:
        v = (v or "").strip()
        return int(v) if v else None

    def _parse_float(v: str) -> float | None:
        v = (v or "").strip()
        return float(v) if v else None

    metrics: dict = {"source": source or "manual", "import_notes": import_notes, "imported_by": imported_by}
    for key, parser, raw in (
        ("views", _parse_int, views),
        ("unique_visitors", _parse_int, unique_visitors),
        ("avg_time_seconds", _parse_int, avg_time_seconds),
        ("impressions", _parse_int, impressions),
        ("conversions", _parse_int, conversions),
        ("bounce_rate", _parse_float, bounce_rate),
        ("ctr", _parse_float, ctr),
        ("position_avg", _parse_float, position_avg),
    ):
        val = parser(raw)
        if val is not None:
            metrics[key] = val

    snap_date = None
    if snapshot_date.strip():
        try:
            snap_date = date.fromisoformat(snapshot_date.strip())
        except ValueError:
            return templates.TemplateResponse(
                request,
                "analytics_import.html",
                {
                    "request": request,
                    "pub": pub,
                    "status": get_publication_confirmation_status(db, publication_id),
                    "ready": analytics_ready(pub),
                    "errors": ["snapshot_date must be YYYY-MM-DD"],
                    "form": form,
                    "title": f"Import metrics — publication #{publication_id}",
                    "feature_flags": all_flags(),
                },
                status_code=422,
            )

    try:
        create_snapshot(
            db,
            publication_id,
            metrics,
            snapshot_date=snap_date,
            imported_by=imported_by or "operator",
        )
    except AnalyticsValidationError as exc:
        return templates.TemplateResponse(
            request,
            "analytics_import.html",
            {
                "request": request,
                "pub": pub,
                "status": get_publication_confirmation_status(db, publication_id),
                "ready": analytics_ready(pub),
                "errors": [str(exc)],
                "form": form,
                "title": f"Import metrics — publication #{publication_id}",
                "feature_flags": all_flags(),
            },
            status_code=422,
        )

    return RedirectResponse(f"/admin/publications/{publication_id}", status_code=303)
