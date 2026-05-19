"""Labels for historical / test publish failures (admin display)."""

from app.models.publish_run import PublishRun
from app.models.publish_target import PublishTarget


def publish_failure_kind(run: PublishRun, target: PublishTarget | None = None) -> str | None:
    """Return badge kind: historical_env, test_target, or None."""
    msg = (run.error_message or "").lower()
    name = (target.name if target else "").lower()
    if target and not target.enabled:
        return "test_target"
    if "env variable" in msg and "not set" in msg:
        return "historical_env"
    if "bad_token" in name or "test-bad" in name:
        return "test_target"
    return None
