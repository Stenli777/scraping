"""Shared repository safety checks — read-only."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(os.environ.get("SCRAP_ROOT", "/opt/scrap"))
MAX_FILE_MB = 10

TMP_PATTERNS = [
    "tmp_*.py",
    "tmp_*.sh",
    "tmp_*.json",
    "tmp_*.log",
    "deploy*.tar.gz",
    "deploy*.zip",
    "_deploy_*.py",
]
FORBIDDEN_TRACKED = [
    ".env",
    "storage/",
    "logs/",
    ".venv/",
]


def _git(*args: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
    )
    return (r.stdout or "") + (r.stderr or "")


def find_tmp_artifacts() -> list[str]:
    found: list[str] = []
    for pat in TMP_PATTERNS:
        found.extend(str(p.relative_to(ROOT)) for p in ROOT.glob(pat))
    for d in ("cursor_tmp", ".cursor_tmp", "artifacts", "tmp_artifacts"):
        p = ROOT / d
        if p.is_dir() and any(p.iterdir()):
            found.append(f"{d}/")
    return sorted(set(found))


def find_tracked_secrets() -> list[str]:
    issues: list[str] = []
    tracked = _git("ls-files").splitlines()
    for path in tracked:
        if path == ".env.example":
            continue
        if path == ".env" or path.startswith(".env.") and not path.endswith(".example"):
            issues.append(f"tracked env file: {path}")
        if path.startswith("storage/") or path.startswith("logs/"):
            if not path.endswith(".gitkeep"):
                issues.append(f"tracked runtime path: {path}")
    return issues


def find_large_tracked_files() -> list[str]:
    issues: list[str] = []
    for path in _git("ls-files").splitlines():
        full = ROOT / path
        if full.is_file():
            mb = full.stat().st_size / (1024 * 1024)
            if mb > MAX_FILE_MB:
                issues.append(f"large tracked file: {path} ({mb:.1f} MB)")
    return issues


def git_clean() -> bool:
    return "nothing to commit" in _git("status") or not _git("status --porcelain").strip()


def git_dirty_summary() -> dict[str, int | str]:
    """Actionable summary for pre-deploy / ops hygiene."""
    porcelain = _git("status", "--porcelain").strip().splitlines()
    modified = sum(1 for ln in porcelain if ln.startswith(" M") or ln.startswith("M "))
    untracked = sum(1 for ln in porcelain if ln.startswith("??"))
    return {
        "dirty": bool(porcelain),
        "changed_files": len(porcelain),
        "modified": modified,
        "untracked": untracked,
        "branch": git_branch(),
        "head": git_head(),
        "hint": "On hermes: review git status, commit deploy bundle, or stash WIP before smoke git_clean.",
    }


def git_branch() -> str:
    return _git("branch", "--show-current").strip() or "unknown"


def git_head() -> str:
    return _git("rev-parse", "--short", "HEAD").strip()


def origin_configured() -> bool:
    return "origin" in _git("remote", "-v")


def branch_tracks_remote() -> bool:
    out = _git("status", "-sb")
    return "[" in out and ("origin/" in out or "ahead" in out or "behind" in out or "..." not in out)


def detached_head() -> bool:
    return _git("symbolic-ref", "-q", "HEAD").strip() == ""


def uncommitted_migrations() -> list[str]:
    out = _git("status", "--porcelain")
    return [ln for ln in out.splitlines() if "alembic/versions" in ln and ln.strip()]
