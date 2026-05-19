#!/usr/bin/env python3
"""Smoke: admin document detail page returns 200 when documents exist."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")


def main() -> int:
    from app.db.session import SessionLocal
    from app.models.parsed_document import ParsedDocument

    db = SessionLocal()
    try:
        doc = db.query(ParsedDocument).order_by(ParsedDocument.id.desc()).first()
        if not doc:
            print("[PASS] admin_document_detail — skip (no documents in DB)")
            return 0
        document_id = doc.id
    finally:
        db.close()

    path = f"/admin/documents/{document_id}"
    try:
        req = urllib.request.Request(BASE + path)
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except Exception as exc:
        print(f"[FAIL] admin_document_detail {path} — {exc}")
        return 1

    ok = code == 200
    print(f"[{'PASS' if ok else 'FAIL'}] admin_document_detail {path} — {code}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
