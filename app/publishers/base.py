from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models.publish_target import PublishTarget


@dataclass
class PublisherResult:
    success: bool
    status: str
    dry_run: bool = False
    endpoint_url: str | None = None
    response_status_code: int | None = None
    response_body: str | None = None
    external_id: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BasePublisher(ABC):
    @abstractmethod
    def publish(
        self,
        target: PublishTarget,
        payload: dict[str, Any],
        *,
        dry_run: bool,
        timeout_seconds: int,
    ) -> PublisherResult:
        pass
