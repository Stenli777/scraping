#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.content_quality_score import ContentQualityScore
from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.parsed_document import ParsedDocument
from app.models.review_result import ReviewResult
from app.models.seo_metadata import SeoMetadata
from app.services.publish_readiness_service import get_publish_readiness
from app.services.strategy_gate_service import get_strategy_readiness


def inspect(doc_id: int) -> None:
    with SessionLocal() as db:
        d = db.get(ParsedDocument, doc_id)
        if not d:
            print(f"doc {doc_id} missing")
            return
        seo = db.scalar(select(SeoMetadata).where(SeoMetadata.document_id == doc_id).order_by(SeoMetadata.id.desc()))
        review = db.scalar(select(ReviewResult).where(ReviewResult.document_id == doc_id).order_by(ReviewResult.id.desc()))
        qc = db.scalar(
            select(ContentQualityScore).where(ContentQualityScore.document_id == doc_id).order_by(ContentQualityScore.id.desc())
        )
        rcs = db.scalars(
            select(ContentReleaseCandidate)
            .where(ContentReleaseCandidate.document_id == doc_id)
            .order_by(ContentReleaseCandidate.id.desc())
            .limit(5)
        ).all()
        print(f"=== doc #{doc_id} ===")
        print("source_url", (d.source_url or "")[:80])
        print("rewritten", bool(d.rewritten_text and d.rewritten_text.strip()), "chars", len(d.rewritten_text or ""))
        print("editorial", d.editorial_status, "approved_for_publish", d.approved_for_publish, "rev", d.current_revision_number)
        print("seo", "YES" if seo else "MISSING")
        if seo:
            print("  seo_title", seo.seo_title)
            print("  slug", seo.slug)
            print("  description", (seo.seo_description or "")[:80])
            print("  tags", seo.tags_json)
        print("review", "YES" if review else "MISSING", "take", getattr(review, "take", None), "score", getattr(review, "score", None))
        print("quality", "YES" if qc else "MISSING", "verdict", getattr(qc, "verdict", None), "score", getattr(qc, "overall_score", None))
        print("candidates", [(c.id, c.status, c.qa_score, len(c.blocking_issues_json or [])) for c in rcs])
        print("strategy", get_strategy_readiness(db, doc_id))
        print("readiness", get_publish_readiness(db, doc_id))


if __name__ == "__main__":
    for did in sys.argv[1:] or ["8"]:
        inspect(int(did))
        print()
