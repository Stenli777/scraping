#!/usr/bin/env python3
"""Smoke-check project/agent admin pages."""

from __future__ import annotations

import argparse
import sys

import httpx

BASE = "https://scrap.crmflow24.ru"


def check_url(client: httpx.Client, path: str) -> tuple[bool, int]:
    r = client.get(f"{BASE}{path}", follow_redirects=True)
    return r.status_code == 200, r.status_code


def check_body(client: httpx.Client, path: str, must: list[str], must_not: list[str] | None = None) -> tuple[bool, str]:
    r = client.get(f"{BASE}{path}", follow_redirects=True)
    if r.status_code != 200:
        return False, f"status {r.status_code}"
    text = r.text
    for s in must:
        if s not in text:
            return False, f"missing {s!r}"
    for s in must_not or []:
        if s in text:
            return False, f"forbidden {s!r}"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", type=int, default=1)
    args = parser.parse_args()
    pid = args.project_id
    paths = [
        "/admin/agents",
        "/admin/agents/new",
        f"/admin/agents/seo_enrich",
        f"/admin/projects/{pid}/agents",
        f"/admin/projects/{pid}/agents/review_article",
        f"/admin/projects/{pid}/tasks?page_size=10",
    ]
    failed = []
    with httpx.Client(timeout=30) as client:
        for path in paths:
            ok, code = check_url(client, path)
            print(f"[{'PASS' if ok else 'FAIL'}] {path} -> {code}")
            if not ok:
                failed.append(path)
        checks = [
            ("/admin/agents", ["Проект", "Technical key", "admin-table-viewport"], None),
            ("/admin/agents/new", ["project_id", "base_agent", "Custom / manual"], None),
            ("/admin/agents/seo_enrich", ["Операторская сводка", "Проектные настройки", "Usage audit"], None),
            (f"/admin/projects/{pid}/agents/review_article", ["<details", 'name="system"'], ["???"]),
            ("/admin/projects/new", ["form-compact"], None),
        ]
        for path, must, must_not in checks:
            ok, detail = check_body(client, path, must, must_not)
            print(f"[{'PASS' if ok else 'FAIL'}] body {path} -> {detail}")
            if not ok:
                failed.append(path)
        ok, _ = check_body(
            client,
            f"/admin/projects/{pid}/agents/review_article?saved=1&activated=1",
            ["alert-success", "сохранена"],
            None,
        )
        print(f"[{'PASS' if ok else 'WARN'}] saved flash markup")
    if failed:
        print(f"FAILED: {len(failed)}")
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
