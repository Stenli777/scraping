#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path("/opt/scrap")


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    run(["git", "add", "-A"])
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True)
    if not status.stdout.strip():
        print("nothing to commit")
        return

    groups = [
        (
            ["alembic/versions/012_automation_scheduler.py", "app/models/automation_rule.py",
             "app/models/automation_run.py", "app/models/scheduler_state.py", "app/models/__init__.py"],
            "feat: add scheduler and automation models",
        ),
        (
            ["app/scheduler", "deploy/scrap-scheduler.service", "app/core/config.py",
             "app/core/feature_flags.py", "app/api/health.py"],
            "feat: add scheduler engine and heartbeat",
        ),
        (
            ["app/services/automation_service.py", "app/api/automation.py", "app/main.py"],
            "feat: add controlled automation workflows",
        ),
        (
            ["app/admin", "scripts/smoke/check_scheduler.py", "scripts/smoke/run_all.py", ".env.example"],
            "feat: add automation admin and API",
        ),
        (
            ["docs/"],
            "docs: document scheduler and automation architecture",
        ),
    ]

    for paths, msg in groups:
        existing = [p for p in paths if (ROOT / p).exists() or p.endswith("/")]
        if not existing:
            continue
        subprocess.run(["git", "add"] + paths, cwd=ROOT)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
        if diff.returncode == 0:
            continue
        run(["git", "commit", "-m", msg])

    run(["git", "push"])
    print("git done")


if __name__ == "__main__":
    main()
