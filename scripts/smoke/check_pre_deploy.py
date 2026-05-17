#!/usr/bin/env python3
import os
import subprocess
import sys

ROOT = os.environ.get("SCRAP_ROOT", "/opt/scrap")

def main():
    r = subprocess.run(
        [sys.executable, str(ROOT + "/scripts/pre_deploy_check.py")],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": ROOT},
    )
    ok = r.returncode in (0, 1)
    print(f"[{'PASS' if ok else 'FAIL'}] pre_deploy — exit {r.returncode}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
