#!/usr/bin/env python3
"""Post-deploy validation."""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("SCRAP_ROOT", "/opt/scrap"))
BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")


def check(name: str, ok: bool) -> int:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    return 0 if ok else 1


def main() -> int:
    failed = 0
    for svc in ("scrap-api", "scrap-worker", "scrap-scheduler"):
        r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True)
        failed += check(f"service_{svc}", r.stdout.strip() == "active")

    try:
        with urllib.request.urlopen(BASE + "/health/ready", timeout=15) as resp:
            ready = json.loads(resp.read().decode())
        failed += check("readiness", ready.get("status") in ("ready", "degraded"))
    except Exception as exc:
        print(f"       {exc}")
        failed += 1

    try:
        with urllib.request.urlopen(BASE + "/api/scheduler/status", timeout=10) as resp:
            sched = json.loads(resp.read().decode())
        failed += check("scheduler_status", "scheduler_enabled" in sched)
    except Exception:
        failed += 1

    r = subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/smoke/check_db.py")],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    failed += check("db_smoke", r.returncode == 0)

    media = Path(os.environ.get("MEDIA_STORAGE", "/opt/scrap/storage/media"))
    if not media.is_absolute():
        media = ROOT / media
    failed += check("media_path", media.exists())

    if failed:
        print("FAIL: post-deploy check")
        return 2
    print("PASS: post-deploy check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
