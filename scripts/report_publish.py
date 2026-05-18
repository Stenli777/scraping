#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.publication_record import PublicationRecord
from app.models.publish_run import PublishRun
from app.models.seo_metadata import SeoMetadata

run_id = int(sys.argv[1]) if len(sys.argv) > 1 else 25
cid = int(sys.argv[2]) if len(sys.argv) > 2 else 5

with SessionLocal() as db:
    run = db.get(PublishRun, run_id)
    c = db.get(ContentReleaseCandidate, cid)
    seo = db.scalar(select(SeoMetadata).where(SeoMetadata.document_id == run.document_id).order_by(SeoMetadata.id.desc())) if run else None
    rec = db.scalar(select(PublicationRecord).where(PublicationRecord.document_id == run.document_id).order_by(PublicationRecord.id.desc())) if run else None
    print("RUN", run.id, run.status, "rc", run.release_candidate_id, run.payload_version, run.response_schema_version)
    print("EXT", run.external_id, "URL", run.draft_url, "REMOTE", run.remote_status)
    print("CAND", c.status if c else None, c.published_at if c else None)
    if seo:
        print("TITLE", seo.seo_title)
        print("SLUG", seo.slug)
    if rec:
        print("PUBREC", rec.id, rec.publication_status, rec.external_article_id, rec.external_url)
