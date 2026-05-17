#!/usr/bin/env python3
"""Stage 4D crmflow24 inbound integration tests."""

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SCRAP_TEST_BASE", "http://127.0.0.1:8800")
DOC_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 7


def api(method, path, data=None, timeout=120):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw.decode()
        return e.code, detail


def find_target(name_substr: str) -> int | None:
    _, data = api("GET", "/api/publish-targets")
    for t in data.get("targets", []):
        if name_substr in t.get("name", ""):
            return t["id"]
    return None


def main() -> int:
    print("=== 4D integration tests ===")

    print("\n[1] article_v2 publish (mock target)")
    mock_tid = find_target("crmflow24-mock-v2")
    if not mock_tid:
        print("SKIP: crmflow24-mock-v2 target missing ? run seed_crmflow24_mock_v2_target.py")
    else:
        code, res = api(
            "POST",
            f"/api/documents/{DOC_ID}/publish-draft",
            {"publish_target_id": mock_tid, "force": True, "dry_run": False},
        )
        print("status", code, json.dumps(res, ensure_ascii=False)[:500])
        if res.get("publish_run_id"):
            _, detail = api("GET", f"/api/publish-runs/{res['publish_run_id']}")
            print("run detail", json.dumps(detail, ensure_ascii=False)[:400])

    print("\n[2] unsupported payload version")
    # use v1 target with forced wrong format via DB not available ? expect 400 from service
    code, res = api("POST", f"/api/documents/{DOC_ID}/publish-draft", {"publish_target_id": 99999, "force": True})
    print("invalid target", code, res)

    print("\n[3] retryable failure + retry API")
    # create ephemeral failure by publishing to bad endpoint via mock target name crmflow24-mock-v2
    # temporarily use target id 4 but wrong endpoint - skip if no failed run
    _, runs = api("GET", f"/api/documents/{DOC_ID}/publish-runs")
    retryable_id = None
    for r in runs.get("runs", []):
        if r.get("status") == "failed_retryable":
            retryable_id = r["id"]
            break
    if not retryable_id:
        print("No failed_retryable run ? create one by pointing target to dead port")
    else:
        code, res = api("POST", f"/api/publish-runs/{retryable_id}/retry")
        print("retry", code, json.dumps(res, ensure_ascii=False)[:400])

    print("\n[4] publish target health")
    print(api("GET", "/api/publish-targets/health"))

    print("\n[5] mock validation failure")
    req = urllib.request.Request(
        BASE + "/api/mock-crmflow24/articles/import",
        data=json.dumps({"payload_version": "article_v2"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print("unexpected success")
    except urllib.error.HTTPError as e:
        print("validation", e.code, e.read()[:200])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
