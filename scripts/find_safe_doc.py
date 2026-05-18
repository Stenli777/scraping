#!/usr/bin/env python3
"""List non-test documents suitable for a production release candidate (read-only).

Safety:
- read-only by default
- does not modify CRMFlow24
- does not publish
- does not print secrets
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.content_quality_score import ContentQualityScore
from app.models.parsed_document import ParsedDocument
from app.models.review_result import ReviewResult
from app.models.seo_metadata import SeoMetadata
from app.services.strategy_gate_service import detect_test_document, document_strategy_allowed


def main() -> int:
    with SessionLocal() as db:
        docs = db.scalars(select(ParsedDocument).order_by(ParsedDocument.id.asc())).all()
        candidates: list[tuple] = []
        for d in docs:
            if not d.rewritten_text or len((d.rewritten_text or "").strip()) < 200:
                continue
            seo = db.scalar(
                select(SeoMetadata).where(SeoMetadata.document_id == d.id).order_by(SeoMetadata.id.desc())
            )
            review = db.scalar(
                select(ReviewResult).where(ReviewResult.document_id == d.id).order_by(ReviewResult.id.desc())
            )
            qc = db.scalar(
                select(ContentQualityScore)
                .where(ContentQualityScore.document_id == d.id)
                .order_by(ContentQualityScore.id.desc())
            )
            title = (seo.seo_title if seo else None) or (seo.h1 if seo else None) or (d.metadata_json or {}).get("title") or ""
            slug = (seo.slug if seo else "") or ""
            is_test, _ = detect_test_document(title=title, text=d.rewritten_text or "", slug=slug)
            if is_test:
                continue
            ok, block, _ = document_strategy_allowed(db, d.id)
            score = 0
            if seo and seo.slug:
                score += 2
            if review and review.take is True:
                score += 2
            if qc and qc.verdict == "approved":
                score += 3
            if d.approved_for_publish:
                score += 2
            if ok:
                score += 2
            candidates.append(
                (score, d.id, title[:60], bool(seo), review.take if review else None, qc.verdict if qc else None, d.editorial_status)
            )
        candidates.sort(reverse=True)
        print("Top safe-ish documents (score desc):")
        for row in candidates[:15]:
            print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
