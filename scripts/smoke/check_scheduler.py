#!/usr/bin/env python3
"""Scheduler and async automation smoke checks."""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")


def check(name, ok, detail=""):
    line = f"[{'PASS' if ok else 'FAIL'}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return 0 if ok else 1


def get_json(path, timeout=15):
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


def post_json(path, timeout=15):
    try:
        req = urllib.request.Request(BASE + path, method="POST", data=b"")
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


def main():
    failed = 0
    ok, status, err = get_json("/api/scheduler/status")
    failed += check("scheduler_status", ok, err or str(status.get("scheduler_enabled")))
    if ok:
        failed += check("scheduler_fields", "queued_runs" in status and "running_runs" in status)

    ok2, ready, _ = get_json("/health/ready")
    if ok2 and status.get("scheduler_enabled"):
        failed += check("ready_scheduler", ready.get("scheduler", {}).get("status") == "ok" or ready.get("checks", {}).get("scheduler") == "ok")
    else:
        failed += check("ready_ok", ok2 and ready.get("status") in ("ready", "degraded"))

    # non-destructive: only verify rules list if automation on
    if status.get("automation_enabled"):
        ok3, rules, _ = get_json("/api/automation/rules")
        failed += check("automation_rules", ok3)
        if ok3 and rules.get("rules"):
            rid = rules["rules"][0]["id"]
            t0 = time.time()
            ok4, res, err4 = post_json(f"/api/automation/rules/{rid}/run")
            elapsed = time.time() - t0
            failed += check("async_manual_enqueue", ok4 and elapsed < 5, f"elapsed={elapsed:.2f}s status={res.get('status')}")
            if ok4 and res.get("automation_run_id"):
                run_id = res["automation_run_id"]
                ok5, _, _ = post_json(f"/api/automation/runs/{run_id}/cancel")
                failed += check("cancel_queued", ok5)
    else:
        failed += check("automation_disabled_skip", True, "skipped enqueue test")

    return failed


if __name__ == "__main__":
    sys.exit(main())
