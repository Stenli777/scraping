#!/usr/bin/env python3
"""Smoke-check project/agent admin pages."""

from __future__ import annotations

import argparse
import sys

import httpx

BASE = "https://scrap.crmflow24.ru"

PATHS = [
    "/admin/projects",
    "/admin/projects/new",
    "/admin/agents",
    "/admin/agents/new",
    "/admin/agents/quality_review",
    "/admin/prompts/quality_review",
]


def check_url(client: httpx.Client, path: str) -> tuple[bool, int, str]:
    r = client.get(f"{BASE}{path}", follow_redirects=True)
    return r.status_code == 200, r.status_code, str(r.url)


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
    parser.add_argument("--project-id", type=int, default=1)
    args = parser.parse_args()
    pid = args.project_id

    paths = list(PATHS) + [
        f"/admin/projects/{pid}/edit",
        f"/admin/projects/{pid}/agents",
        f"/admin/projects/{pid}/tasks",
        f"/admin/projects/{pid}/tasks?page_size=10",
        f"/admin/projects/{pid}/documents?page_size=50",
        f"/api/projects/{pid}/agents/quality_review/effective-prompt",
    ]
    failed: list[str] = []
    with httpx.Client(timeout=30) as client:
        for path in paths:
            ok, code, final = check_url(client, path)
            print(f"[{'PASS' if ok else 'FAIL'}] {path} -> {code}")
            if not ok:
                failed.append(path)

        checks = [
            (
                f"/admin/projects/{pid}/agents/review_article",
                [
                    "Сохранить новую версию агента",
                    "Сохранить и сделать активной для проекта",
                    'name="system"',
                    "<details",
                ],
                [],
            ),
            (
                f"/admin/projects/{pid}/agents/topic_cleanup_v1",
                ["fallback", "<details"],
                ["???"],
            ),
            (
                f"/admin/projects/new",
                ["form-compact", "form-row"],
                [],
            ),
            (
                f"/admin/projects/{pid}/tasks?page_size=100",
                ["page_size", "page-size-select", "10", "50", "100", "admin-table-viewport"],
                [],
            ),
            (
                f"/admin/projects/{pid}/documents",
                ["admin-select", "admin-table-viewport", "page_size"],
                [],
            ),
        ]
        for path, must, must_not in checks:
            ok, detail = check_body(client, path, must, must_not)
            print(f"[{'PASS' if ok else 'FAIL'}] body {path} -> {detail}")
            if not ok:
                failed.append(path)

    if failed:
        print(f"FAILED: {len(failed)}")
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
