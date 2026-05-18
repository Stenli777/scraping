#!/usr/bin/env python3
"""Stage 4F: production CRMFlow24 smoke publish + idempotency."""

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SCRAP_TEST_BASE", "http://127.0.0.1:8800")
SMOKE_TITLE = "Smoke test Scrap to CRMFlow24 production - ???????"


def call(method, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        BASE + path, data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.read() else {}


def main():
    from app.db.session import SessionLocal
    from app.models.publish_target import PublishTarget
    from app.models.seo_metadata import SeoMetadata

    doc_id = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    db = SessionLocal()
    target = db.query(PublishTarget).filter(PublishTarget.name == "crmflow24-production-v2").first()
    if not target:
        print("production target missing")
        return 1
    tid = target.id
    seo = db.query(SeoMetadata).filter(SeoMetadata.document_id == doc_id).order_by(SeoMetadata.id.desc()).first()
    orig_h1 = seo.h1 if seo else None
    if seo:
        seo.h1 = SMOKE_TITLE
        seo.seo_title = SMOKE_TITLE
        db.commit()
    db.close()

    print("publish 1", call("POST", f"/api/documents/{doc_id}/publish-draft", {
        "publish_target_id": tid, "force": True, "dry_run": False,
    }))
    print("publish 2 (idempotency)", call("POST", f"/api/documents/{doc_id}/publish-draft", {
        "publish_target_id": tid, "force": True, "dry_run": False,
    }))

    if seo and orig_h1 is not None:
        db = SessionLocal()
        seo2 = db.get(SeoMetadata, seo.id)
        if seo2:
            seo2.h1 = orig_h1
            db.commit()
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
