from app.models.publish_target import PublishTarget
from app.publishers.base import BasePublisher
from app.publishers.exceptions import PublishError
from app.publishers.mock import MockPublisher
from app.publishers.webhook import WebhookPublisher

_PUBLISHERS: dict[str, BasePublisher] = {
    "mock": MockPublisher(),
    "webhook": WebhookPublisher(),
    "crmflow24": WebhookPublisher(),
}


def get_publisher(target: PublishTarget) -> BasePublisher:
    publisher = _PUBLISHERS.get(target.target_type)
    if not publisher:
        raise PublishError(f"Unknown publish target_type: {target.target_type}")
    return publisher
