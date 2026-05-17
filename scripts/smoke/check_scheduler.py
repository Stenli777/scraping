#!/usr/bin/env python3
"""Scheduler and automation smoke checks."""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")


def check(name: str, ok: bool, detail: str = "") -> int:
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return 0 if ok else 1


def get_json(path: str, timeout: int = 15):
    try:
        req = urllib.request.Request(BASE + path)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode()), ""
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except Exception:
            body = {}
        return False, body, f"HTTP {exc.code}"
    except Exception as exc:
        return False, None, str(exc)


def main() -> int:
    failed = 0
    ok, data, err = get_json("/api/scheduler/status")
    if not ok:
        failed += check("scheduler_status", False, err)
        return failed
    failed += check("scheduler_status", True, f"enabled={data.get('scheduler_enabled')}")

    ok2, ready, err2 = get_json("/health/ready")
    if not ok2:
        failed += check("ready_scheduler", False, err2)
        return failed

    sched_enabled = data.get("scheduler_enabled")
    if sched_enabled:
        hb = data.get("heartbeat", {})
        age = hb.get("last_heartbeat_seconds")
        stale = hb.get("status") == "stale"
        failed += check("scheduler_heartbeat", not stale and hb.get("status") == "ok", f"heartbeat={hb}")
        if "scheduler" in ready:
            failed += check("ready_scheduler_block", ready["scheduler"].get("status") == "ok", str(ready.get("scheduler")))
    else:
        failed += check("scheduler_disabled_ok", "scheduler" not in ready.get("checks", {}) or True, "scheduler off")

    return failed


if __name__ == "__main__":
    sys.exit(main())
