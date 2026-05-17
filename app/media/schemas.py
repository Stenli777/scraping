from dataclasses import dataclass, field
from typing import Any


@dataclass
class MediaPromptBundle:
    prompt: str
    alt_text: str
    caption: str


@dataclass
class MediaGenerateResult:
    success: bool
    storage_path: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    checksum: str | None = None
    public_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
