"""Workspace validation — hermes /opt/scrap guardrails."""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

from app.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def get_workspace_warnings() -> list[str]:
    settings = get_settings()
    warnings: list[str] = []
    host = socket.gethostname().lower()
    allowed = [h.strip().lower() for h in settings.expected_hostname.split(",") if h.strip()]
    if allowed and not any(a in host for a in allowed):
        warnings.append(
            f"Non-production workspace: hostname={socket.gethostname()} (expected contains '{settings.expected_hostname}')"
        )
    resolved = str(PROJECT_ROOT.resolve())
    expected_path = str(Path(settings.expected_project_path).resolve())
    if resolved != expected_path:
        warnings.append(
            f"Non-production workspace: project_path={resolved} (expected {expected_path})"
        )
    return warnings


def get_workspace_info() -> dict:
    settings = get_settings()
    status = _git("status", "--porcelain")
    clean = not status
    branch = _git("branch", "--show-current") or "unknown"
    head = _git("rev-parse", "HEAD")
    short = _git("rev-parse", "--short", "HEAD")
    return {
        "hostname": socket.gethostname(),
        "project_path": str(PROJECT_ROOT.resolve()),
        "expected_hostname": settings.expected_hostname,
        "expected_project_path": settings.expected_project_path,
        "git_branch": branch,
        "git_clean": clean,
        "git_head": head,
        "git_head_short": short,
        "git_status_porcelain": status.splitlines() if status else [],
        "warnings": get_workspace_warnings(),
        "cwd": os.getcwd(),
    }
