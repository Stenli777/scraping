import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def fetch_url(url: str) -> str:
    """Fetch HTML using Scrapling when available, otherwise httpx."""
    settings = get_settings()
    try:
        from scrapling.fetchers import Fetcher

        logger.info("Fetching via Scrapling Fetcher: %s", url)
        page = Fetcher.get(url, stealthy_headers=True, timeout=settings.http_timeout_seconds)
        html = page.html_content if hasattr(page, "html_content") else str(page)
        if html:
            return html
    except Exception as exc:
        logger.warning("Scrapling fetch failed, fallback to httpx: %s", exc)

    with httpx.Client(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": settings.http_user_agent},
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text
