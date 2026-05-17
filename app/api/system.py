"""System / workspace API."""

from fastapi import APIRouter

from app.core.feature_flags import is_automation_enabled, is_scheduler_enabled
from app.core.workspace import get_workspace_info, get_workspace_warnings

router = APIRouter(tags=["system"])


@router.get("/api/system/workspace")
def api_workspace():
    info = get_workspace_info()
    return {
        "hostname": info["hostname"],
        "project_path": info["project_path"],
        "git_branch": info["git_branch"],
        "git_clean": info["git_clean"],
        "git_head_short": info["git_head_short"],
        "warnings": info["warnings"],
        "scheduler_enabled": is_scheduler_enabled(),
        "automation_enabled": is_automation_enabled(),
    }
