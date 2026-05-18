#!/usr/bin/env python3
"""Retention report / optional cleanup for llm_enrichment_jobs. Default: dry-run only."""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "/opt/scrap")

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.llm_enrichment_job import EnrichmentJobStatus, LlmEnrichmentJob


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrichment jobs retention report/cleanup")
    parser.add_argument("--older-than-days", type=int, default=None, help="Age threshold (default from config)")
    parser.add_argument("--status", action="append", default=[], help="Filter statuses (repeatable)")
    parser.add_argument("--execute", action="store_true", help="Actually delete (default: dry-run)")
    args = parser.parse_args()

    settings = get_settings()
    days = args.older_than_days if args.older_than_days is not None else settings.enrichment_retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    statuses = args.status or [
        EnrichmentJobStatus.COMPLETED,
        EnrichmentJobStatus.CANCELLED,
        EnrichmentJobStatus.FAILED_TERMINAL,
        EnrichmentJobStatus.SKIPPED,
    ]

    db = SessionLocal()
    try:
        q = select(LlmEnrichmentJob).where(
            LlmEnrichmentJob.created_at < cutoff,
            LlmEnrichmentJob.status.in_(statuses),
        )
        jobs = list(db.scalars(q).all())
        print(f"dry_run={not args.execute} older_than_days={days} cutoff={cutoff.isoformat()}")
        print(f"candidates={len(jobs)} statuses={statuses}")
        for job in jobs[:20]:
            print(f"  id={job.id} status={job.status} doc={job.document_id} created={job.created_at}")
        if len(jobs) > 20:
            print(f"  ... and {len(jobs) - 20} more")

        if args.execute and jobs:
            for job in jobs:
                db.delete(job)
            db.commit()
            print(f"deleted={len(jobs)}")
        elif args.execute:
            print("deleted=0")
        else:
            print("No rows deleted (dry-run). Pass --execute to delete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
