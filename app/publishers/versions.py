"""Payload version negotiation for publish targets."""

from app.publishers.validators import PAYLOAD_VERSION as ARTICLE_V1
from app.publishers.validators_v2 import PAYLOAD_VERSION as ARTICLE_V2

SUPPORTED_PAYLOAD_FORMATS = frozenset({ARTICLE_V1, ARTICLE_V2})
DEFAULT_PAYLOAD_FORMAT = ARTICLE_V1


def normalize_payload_format(payload_format: str | None) -> str:
    fmt = (payload_format or DEFAULT_PAYLOAD_FORMAT).strip()
    if fmt not in SUPPORTED_PAYLOAD_FORMATS:
        raise ValueError(f"Unsupported payload_format: {fmt}")
    return fmt


def is_supported_payload_format(payload_format: str | None) -> bool:
    return (payload_format or DEFAULT_PAYLOAD_FORMAT).strip() in SUPPORTED_PAYLOAD_FORMATS
