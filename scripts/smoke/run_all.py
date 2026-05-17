#!/usr/bin/env python3
"""Run all smoke checks — read-only by default."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path("/opt/scrap")
CHECKS = [
    "check_health.py",
    "check_ready.py",
    "check_db.py",
    "check_cliproxy.py",
    "check_pipeline.py",
    "check_media.py",
    "check_publish.py",
    "check_scheduler.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrap smoke tests")
    parser.add_argument("--execute", action="store_true", help="Allow destructive checks (not implemented)")
    args = parser.parse_args()
    if args.execute:
        print("WARN: --execute has no extra destructive checks in 3C")

    failed = 0
    print("=== Scrap smoke tests ===")
    for name in CHECKS:
        script = ROOT / "scripts" / "smoke" / name
        r = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
        )
        failed += r.returncode

    print("=== Summary ===")
    if failed:
        print(f"FAIL: {failed} check(s) failed")
        return 1
    print("PASS: all smoke checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
