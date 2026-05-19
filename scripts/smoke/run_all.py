#!/usr/bin/env python3
"""Run all smoke checks — read-only by default; production checks opt-in.

Safety:
- default: never hits production publish endpoint
- production: only with --include-production
- does not print secrets
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path("/opt/scrap")
CHECKS_DEFAULT = [
    "check_pre_deploy.py",
    "check_workspace.py",
    "check_repo_safety.py",
    "check_health.py",
    "check_admin_discovered.py",
    "check_ready.py",
    "check_db.py",
    "check_cliproxy.py",
    "check_pipeline.py",
    "check_media.py",
    "check_publish.py",
    "check_scheduler.py",
    "check_pilots.py",
]
CHECKS_PRODUCTION = [
    "check_crmflow24_production_target.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrap smoke tests")
    parser.add_argument(
        "--include-production",
        action="store_true",
        help="Run production target health checks (no publish)",
    )
    parser.add_argument("--execute", action="store_true", help="Reserved for future destructive checks")
    args = parser.parse_args()

    checks = list(CHECKS_DEFAULT)
    if args.include_production:
        checks.extend(CHECKS_PRODUCTION)
    else:
        print("INFO: production publish target checks skipped (use --include-production)")

    if args.execute:
        print("WARN: --execute has no extra destructive checks")

    failed = 0
    print("=== Scrap smoke tests ===")
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    for name in checks:
        script = ROOT / "scripts" / "smoke" / name
        r = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), env=env)
        failed += r.returncode

    print("=== Summary ===")
    if failed:
        print(f"FAIL: {failed} check(s) failed")
        return 1
    print("PASS: all smoke checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
