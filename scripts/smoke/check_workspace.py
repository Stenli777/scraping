#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")


def main():
    try:
        with urllib.request.urlopen(BASE + "/api/system/workspace", timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        print(f"[FAIL] workspace_endpoint — {exc}")
        return 1
    ok = data.get("hostname") and data.get("project_path") == "/opt/scrap"
    host_ok = any(x in (data.get("hostname") or "").lower() for x in ("hermes", "psychedelic"))
    print(f"[{'PASS' if ok and host_ok else 'FAIL'}] workspace_endpoint — host={data.get('hostname')} path={data.get('project_path')}")
    return 0 if ok and host_ok else 1

if __name__ == "__main__":
    sys.exit(main())
