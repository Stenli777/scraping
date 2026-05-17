#!/usr/bin/env python3
"""Manual stage 2B rewrite tests — run on server: PYTHONPATH=/opt/scrap python scripts/test_2b_rewrite.py [mock|cliproxy|degraded]"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8800"
TEST_URL = "https://saltpro.ru/articles/vibecode/"


def request(method: str, path: str, data: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def wait_task(task_id: int, timeout: int = 180) -> dict:
    for _ in range(timeout // 2):
        task = request("GET", f"/api/tasks/{task_id}")
        if task["status"] in ("done", "error", "failed_retryable"):
            return task
        time.sleep(2)
    raise TimeoutError(f"Task {task_id} did not finish")


def run_pipeline_test(label: str) -> None:
    print(f"=== {label} ===")
    health = request("GET", "/health")
    ready = request("GET", "/health/ready")
    print("health", health)
    print("ready", ready)

    task = request("POST", "/api/tasks", {"source_url": TEST_URL, "parser_type": "generic_article"})
    tid = task["id"]
    print("task_id", tid)
    finished = wait_task(tid)
    print("status", finished["status"], "error", finished.get("error_message"))
    doc_id = finished.get("document_id")
    if doc_id:
        doc = request("GET", f"/api/documents/{doc_id}")
        rw = (doc.get("rewritten_text") or "")[:120]
        print("rewritten_prefix", repr(rw))
        meta = doc.get("metadata_json") or {}
        print("rewrite_meta", meta.get("rewrite"))


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "mock"
    if mode not in ("mock", "cliproxy", "degraded"):
        print("Usage: test_2b_rewrite.py [mock|cliproxy|degraded]")
        sys.exit(1)
    run_pipeline_test(mode)


if __name__ == "__main__":
    main()
