#!/usr/bin/env python3
"""Read-only pilot consistency checks."""

from __future__ import annotations

import json
import sys

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.content_pilot import ContentPilotItem
from app.models.content_release_candidate import ContentReleaseCandidate
from app.models.parsed_document import ParsedDocument
from app.models.publication_record import PublicationRecord
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.services.release_candidate_service import RC_ARCHIVED


def main() -> int:
    db = SessionLocal()
    issues: list[dict] = []
    warnings: list[dict] = []

    items = db.scalars(select(ContentPilotItem)).all()
    for item in items:
        doc = db.get(ParsedDocument, item.document_id)
        if not doc:
            issues.append({"type": "missing_document", "item_id": item.id, "document_id": item.document_id})

        if item.release_candidate_id:
            rc = db.get(ContentReleaseCandidate, item.release_candidate_id)
            if not rc:
                issues.append({"type": "missing_rc", "item_id": item.id, "rc_id": item.release_candidate_id})
            elif rc.status == RC_ARCHIVED:
                warnings.append({"type": "archived_rc", "item_id": item.id, "rc_id": rc.id})

        if item.publication_record_id:
            pub = db.get(PublicationRecord, item.publication_record_id)
            if not pub:
                issues.append({"type": "missing_publication", "item_id": item.id})
            elif item.status in ("public_confirmed", "analytics_started", "done") and not pub.public_confirmed_at:
                warnings.append({"type": "status_public_without_confirm", "item_id": item.id})

        if item.status == "done":
            pub = db.scalar(
                select(PublicationRecord).where(PublicationRecord.document_id == item.document_id)
            )
            if pub and pub.public_confirmed_at:
                snap = db.scalar(
                    select(AnalyticsSnapshot).where(
                        AnalyticsSnapshot.publication_record_id == pub.id
                    )
                )
                if not snap:
                    warnings.append({"type": "done_without_snapshot", "item_id": item.id})

    dupes = db.execute(
        select(ContentPilotItem.pilot_id, ContentPilotItem.document_id, func.count())
        .group_by(ContentPilotItem.pilot_id, ContentPilotItem.document_id)
        .having(func.count() > 1)
    ).all()
    for pilot_id, document_id, cnt in dupes:
        issues.append({"type": "duplicate_document", "pilot_id": pilot_id, "document_id": document_id, "count": cnt})

    result = {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "items_checked": len(items),
    }
    print(json.dumps(result, indent=2))
    db.close()
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
