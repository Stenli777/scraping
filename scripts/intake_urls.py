#!/usr/bin/env python3
"""Bulk manual trusted URL intake (read-only by default).

Usage:
  PYTHONPATH=/opt/scrap .venv/bin/python scripts/intake_urls.py --project-id 1 --url https://autobit24.ru/blog/...
  PYTHONPATH=/opt/scrap .venv/bin/python scripts/intake_urls.py --project-id 1 --file /tmp/urls.txt
  PYTHONPATH=/opt/scrap .venv/bin/python scripts/intake_urls.py --project-id 1 --file urls.txt --enqueue
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.services.manual_url_intake_service import intake_manual_url, intake_manual_urls_bulk


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual trusted URL intake")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--file", type=str, default=None)
    parser.add_argument("--source-directory-id", type=int, default=None)
    parser.add_argument("--enqueue", action="store_true")
    parser.add_argument("--no-score", action="store_true")
    args = parser.parse_args()

    urls: list[str] = list(args.url)
    if args.file:
        urls.extend(Path(args.file).read_text(encoding="utf-8").splitlines())

    if not urls:
        print("No URLs provided", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        if len(urls) == 1:
            results = [
                intake_manual_url(
                    db,
                    project_id=args.project_id,
                    url=urls[0],
                    source_directory_id=args.source_directory_id,
                    score_quality=not args.no_score,
                    enqueue=args.enqueue,
                )
            ]
        else:
            results = intake_manual_urls_bulk(
                db,
                project_id=args.project_id,
                urls=urls,
                source_directory_id=args.source_directory_id,
                score_quality=not args.no_score,
                enqueue=args.enqueue,
            )
        db.commit()
        for r in results:
            print(
                f"{r.status:16} id={r.discovered_url_id} article={r.article_likelihood} "
                f"dup={r.duplicate} {r.url[:90]} {r.error or ''}"
            )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
