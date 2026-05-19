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
    "/admin/prompts/quality_review",
]


def check_url(client: httpx.Client, path: str) -> tuple[bool, int, str]:
    r = client.get(f"{BASE}{path}", follow_redirects=True)
    ok = r.status_code == 200
    return ok, r.status_code, str(r.url)


def check_body(client: httpx.Client, path: str, must: list[str], must_not: list[str]) -> tuple[bool, str]:
    r = client.get(f"{BASE}{path}", follow_redirects=True)
    if r.status_code != 200:
        return False, f"status {r.status_code}"
    text = r.text
    for s in must:
        if s not in text:
            return False, f"missing: {s!r}"
    for s in must_not:
        if s in text:
            return False, f"forbidden: {s!r}"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-test-project", action="store_true", help="Not implemented in MVP")
    parser.add_argument("--project-id", type=int, default=1)
    args = parser.parse_args()

    if args.create_test_project:
        print("WARN: --create-test-project not implemented; use admin UI")
        return 0

    pid = args.project_id
    paths = list(PATHS) + [
        f"/admin/projects/{pid}/edit",
        f"/admin/projects/{pid}/agents",
        f"/admin/projects/{pid}/tasks",
        f"/admin/projects/{pid}/documents",
        f"/api/projects/{pid}/agents/quality_review/effective-prompt",
    ]
    failed: list[str] = []
    with httpx.Client(timeout=30) as client:
        for path in paths:
            ok, code, final = check_url(client, path)
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {path} -> {code} {final}")
            if not ok:
                failed.append(path)

        agent_checks = [
            (
                f"/admin/projects/{pid}/agents/review_article",
                ["Сохранить новую версию агента", "Сохранить и сделать активной для проекта", 'name="system"', 'name="user"'],
                [],
            ),
            (
                f"/admin/projects/{pid}/agents/topic_cleanup_v1",
                ["fallback"],
                ["???"],
            ),
        ]
        for path, must, must_not in agent_checks:
            ok, detail = check_body(client, path, must, must_not)
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] body {path} -> {detail}")
            if not ok:
                failed.append(path)

    if failed:
        print(f"FAILED: {len(failed)}")
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
