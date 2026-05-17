#!/usr/bin/env python3
"""
Stage 2F end-to-end check via Scrap API only (no Hermes, no auto-publish).

  python scripts/test_2f_e2e.py           # read-only summary
  python scripts/test_2f_e2e.py --execute # discovery (limit 5) + enqueue one URL
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8800"
PROJECT_SLUG = "crmflow24"


def api(method: str, path: str, data: dict | None = None, timeout: int = 120):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw.decode()
        return e.code, detail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Run discovery+enqueue (safe limits)")
    args = parser.parse_args()

    print("=== Scrap 2F E2E (read-only) ===")
    code, health = api("GET", "/health")
    print("health", code, health)

    code, ready = api("GET", "/health/ready")
    print("ready", code, ready.get("status") if isinstance(ready, dict) else ready)

    code, dirs = api("GET", "/api/source-directories")
    if code != 200:
        print("source-directories failed", code, dirs)
        return 1
    directories = [d for d in dirs.get("directories", []) if d.get("enabled")]
    print("enabled source_directories", len(directories))

    if not directories:
        print("No enabled source directory — seed crmflow24 first")
        return 1

    target_dir = directories[0]
    for d in directories:
        if "habr" in d.get("name", ""):
            target_dir = d
            break

    print("using directory", target_dir["id"], target_dir["name"], target_dir["base_url"])

    if args.execute:
        print("\n--- execute: discovery (max 5) ---")
        code, disc = api(
            "POST",
            f"/api/source-directories/{target_dir['id']}/discover",
            {"max_urls": 5, "dry_run": False},
        )
        print("discover", code, disc)

        code, found = api("GET", "/api/discovered-urls?status=discovered&source_directory_id=" + str(target_dir["id"]))
        urls = found.get("urls") or [] if code == 200 else []
        if not urls:
            code, found = api("GET", "/api/discovered-urls?source_directory_id=" + str(target_dir["id"]))
            urls = [u for u in (found.get("urls") or []) if u.get("status") in ("discovered", "duplicate")]
        if not urls:
            print("No URL to enqueue — try another source or relax allow_patterns")
            return 0
        uid = urls[0]["id"]
        print("enqueue discovered_url", uid)
        code, enq = api("POST", f"/api/discovered-urls/{uid}/enqueue")
        print("enqueue", code, enq)
        task_id = enq.get("existing_task_id") if isinstance(enq, dict) else None
        if task_id:
            print("waiting for task", task_id, "(poll up to 180s)")
            for _ in range(36):
                time.sleep(5)
                code, tasks = api("GET", f"/api/tasks/{task_id}")
                if code == 200 and tasks.get("status") in ("done", "error", "failed_retryable"):
                    print("task final", tasks.get("status"))
                    doc_id = tasks.get("document_id")
                    if doc_id:
                        _exercise_document(doc_id)
                    return 0
            print("Task still running — open /admin/tasks/" + str(task_id))
    else:
        print("\nDry run only. Use --execute for discovery+enqueue.")

    return 0


def _exercise_document(document_id: int) -> None:
    code, readiness = api("GET", f"/api/documents/{document_id}/publish-readiness")
    print("publish-readiness", code, readiness)

    code, rev = api("POST", f"/api/documents/{document_id}/run-review")
    print("review", code, rev.get("success") if isinstance(rev, dict) else rev)

    code, seo = api("POST", f"/api/documents/{document_id}/run-seo")
    print("seo", code, seo.get("success") if isinstance(seo, dict) else seo)

    code, targets = api("GET", "/api/publish-targets")
    if code == 200 and targets.get("targets"):
        tid = targets["targets"][0]["id"]
        code, pub = api(
            "POST",
            f"/api/documents/{document_id}/publish-draft",
            {"publish_target_id": tid, "dry_run": True},
        )
        print("publish dry-run", code, pub)
    else:
        print("no publish target — skip publish dry-run")


if __name__ == "__main__":
    sys.exit(main())
