#!/usr/bin/env python3
"""Pre-deploy validation — read-only checks before deploy."""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("SCRAP_ROOT", "/opt/scrap"))
BASE = os.environ.get("SCRAP_SMOKE_BASE", "http://127.0.0.1:8800")

sys.path.insert(0, str(ROOT))
from repo_checks import find_tmp_artifacts, git_clean, git_head  # noqa: E402


def check(name: str, ok: bool, level: str = "FAIL") -> None:
    print(f"[{'PASS' if ok else level}] {name}")


def main() -> int:
    failed = 0
    warned = 0

    ok = git_clean()
    check("git_clean", ok)
    failed += 0 if ok else 1

    tmp = find_tmp_artifacts()
    check("no_tmp_artifacts", not tmp, "WARN" if tmp else "PASS")
    warned += 1 if tmp else 0
    for t in tmp:
        print(f"       artifact: {t}")

    env = ROOT / ".env"
    check("env_exists", env.is_file())
    failed += 0 if env.is_file() else 1

    r = subprocess.run(
        [str(ROOT / ".venv/bin/alembic"), "current"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check("alembic_current", r.returncode == 0)
    if r.returncode != 0:
        failed += 1
    else:
        print(f"       {r.stdout.strip()}")

    r2 = subprocess.run(
        [str(ROOT / ".venv/bin/alembic"), "heads"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    pending = r2.returncode == 0 and "(head)" not in r.stdout and r2.stdout.strip()
    check("migrations_at_head", r.returncode == 0 and not pending)
    if pending:
        warned += 1

    try:
        with urllib.request.urlopen(BASE + "/health", timeout=10) as resp:
            data = json.loads(resp.read().decode())
        ok_h = data.get("status") == "ok"
    except Exception as exc:
        ok_h = False
        print(f"       health error: {exc}")
    check("health_ok", ok_h)
    failed += 0 if ok_h else 1

    storage = ROOT / "storage"
    try:
        storage.mkdir(parents=True, exist_ok=True)
        test = storage / ".pre_deploy_write"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        ok_s = True
    except Exception as exc:
        ok_s = False
        print(f"       storage: {exc}")
    check("storage_writable", ok_s)
    failed += 0 if ok_s else 1

    print(f"HEAD={git_head()}")
    if failed:
        print("FAIL: pre-deploy check")
        return 2
    if warned:
        print("WARN: pre-deploy check")
        return 1
    print("PASS: pre-deploy check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
