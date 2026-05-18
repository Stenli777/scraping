#!/usr/bin/env python3
"""Manual analytics snapshot import — no external APIs, no auto polling."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from app.db.session import SessionLocal
from app.services.analytics_service import AnalyticsValidationError, create_snapshot


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Import analytics snapshot for a publication")
    p.add_argument("--publication-id", type=int, required=True)
    p.add_argument("--snapshot-date", type=str, default="")
    p.add_argument("--views", type=int, default=None)
    p.add_argument("--unique-visitors", type=int, default=None)
    p.add_argument("--avg-time-seconds", type=int, default=None)
    p.add_argument("--bounce-rate", type=float, default=None)
    p.add_argument("--ctr", type=float, default=None)
    p.add_argument("--impressions", type=int, default=None)
    p.add_argument("--conversions", type=int, default=None)
    p.add_argument("--position-avg", type=float, default=None)
    p.add_argument("--source", type=str, default="manual")
    p.add_argument("--imported-by", type=str, default="operator")
    p.add_argument("--notes", type=str, default="")
    p.add_argument(
        "--sample",
        action="store_true",
        help="Create clearly marked sample snapshot (testing only)",
    )
    p.add_argument(
        "--skip-ready-check",
        action="store_true",
        help="Allow import when publication is not analytics_ready (testing only)",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()
    metrics: dict = {"source": args.source, "imported_by": args.imported_by}
    if args.notes:
        metrics["import_notes"] = args.notes
    for key, val in (
        ("views", args.views),
        ("unique_visitors", args.unique_visitors),
        ("avg_time_seconds", args.avg_time_seconds),
        ("bounce_rate", args.bounce_rate),
        ("ctr", args.ctr),
        ("impressions", args.impressions),
        ("conversions", args.conversions),
        ("position_avg", args.position_avg),
    ):
        if val is not None:
            metrics[key] = val

    snap_date = date.fromisoformat(args.snapshot_date) if args.snapshot_date else None

    db = SessionLocal()
    try:
        snap = create_snapshot(
            db,
            args.publication_id,
            metrics,
            snapshot_date=snap_date,
            imported_by=args.imported_by,
            require_analytics_ready=not args.skip_ready_check,
            sample=args.sample,
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "snapshot_id": snap.id,
                    "publication_id": args.publication_id,
                    "snapshot_date": str(snap.snapshot_date),
                    "source": snap.source,
                    "sample": bool(args.sample),
                },
                indent=2,
            )
        )
        return 0
    except AnalyticsValidationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
