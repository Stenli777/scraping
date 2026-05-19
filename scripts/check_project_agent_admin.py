#!/usr/bin/env python3
"""Smoke-check project/agent admin pages (read-only by default)."""

from __future__ import annotations

import argparse
import sys

import httpx

BASE = "https://scrap.crmflow24.ru"

PATHS = [
    "/admin/projects",
    "/admin/projects/new",
    "/admin/agents",
    "/admin/agents/quality_review",
    "/admin/prompts/quality_review",  # backward compat redirect
]


def check_url(client: httpx.Client, path: str) -> tuple[bool, int, str]:
    r = client.get(f"{BASE}{path}", follow_redirects=True)
    ok = r.status_code == 200
    final = str(r.url)
    return ok, r.status_code, final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-test-project", action="store_true", help="Not implemented in MVP")
    parser.add_argument("--project-id", type=int, default=1)
    args = parser.parse_args()

    if args.create_test_project:
        print("WARN: --create-test-project not implemented; use admin UI")
        return 0

    paths = list(PATHS) + [
        f"/admin/projects/{args.project_id}/edit",
        f"/admin/projects/{args.project_id}/agents",
        f"/api/projects/{args.project_id}/agents/quality_review/effective-prompt",
    ]
    failed = []
    with httpx.Client(timeout=30) as client:
        for path in paths:
            ok, code, final = check_url(client, path)
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {path} -> {code} {final}")
            if not ok:
                failed.append(path)

    if failed:
        print(f"FAILED: {len(failed)}")
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
