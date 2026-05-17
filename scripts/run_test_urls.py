#!/usr/bin/env python3
"""Create and wait for scraping tasks for test URLs."""

import json
import sys
import time

import httpx

TEST_URLS = [
    "https://saltpro.ru/articles/bitriks24-kedo-reytinge-cnewsmarket-2025/",
    "https://saltpro.ru/articles/bitriks24-vibecode-reliz-2026/",
    "https://saltpro.ru/articles/nalogovaya-reforma-2026-kak-perestroit-biznes-s-bitriks24/",
    "https://www.sotbit.ru/info/bitrix24/nastroyka-crm-bitriks24.html",
    "https://habr.com/ru/companies/bitrix/articles/1031736/",
]

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8800"


def main() -> int:
    client = httpx.Client(timeout=120)
    results = []
    for url in TEST_URLS:
        r = client.post(f"{BASE}/api/tasks", json={"source_url": url})
        r.raise_for_status()
        task = r.json()
        task_id = task["id"]
        print(f"created task {task_id} parser={task.get('parser_type')} url={url}")

        for _ in range(90):
            t = client.get(f"{BASE}/api/tasks/{task_id}").json()
            if t["status"] in ("done", "error"):
                break
            time.sleep(2)
        results.append(t)
        print(f"  -> status={t['status']} doc={t.get('document_id')} err={t.get('error_message')}")

    print("\n=== SUMMARY ===")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    failed = [r for r in results if r["status"] != "done"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
