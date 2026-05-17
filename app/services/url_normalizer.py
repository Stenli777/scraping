"""URL normalization for discovery deduplication."""

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "yclid",
        "gclid",
        "fbclid",
        "from",
        "ref",
    }
)


def normalize_url(url: str) -> str:
    """Normalize URL for dedupe keys."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("URL has no hostname")

    port = parsed.port
    netloc = hostname
    if port and not ((parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)):
        netloc = f"{hostname}:{port}"

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query = _normalize_query(parsed.query)

    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


def _normalize_query(query: str) -> str:
    if not query:
        return ""
    params = parse_qs(query, keep_blank_values=False)
    filtered = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}
    if not filtered:
        return ""
    items: list[tuple[str, str]] = []
    for key in sorted(filtered.keys()):
        for val in filtered[key]:
            items.append((key, val))
    return urlencode(items, doseq=True)


def same_hostname(url: str, base_url: str) -> bool:
    try:
        return urlparse(url).hostname == urlparse(base_url).hostname
    except Exception:
        return False


def resolve_absolute(href: str, base_url: str) -> str | None:
    from urllib.parse import urljoin

    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    return urljoin(base_url, href)


def matches_patterns(url: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    return any(p in url for p in patterns)


def is_blocked(url: str, block_patterns: list[str] | None) -> bool:
    if not block_patterns:
        return False
    lower = url.lower()
    return any(p.lower() in lower for p in block_patterns)
