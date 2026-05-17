"""Sitemap and HTML link extractors for controlled discovery."""

import logging
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import httpx

from app.services.url_normalizer import resolve_absolute, same_hostname

logger = logging.getLogger(__name__)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def fetch_text(url: str, *, timeout: int, user_agent: str) -> tuple[str, int]:
    with httpx.Client(
        timeout=timeout,
        headers={"User-Agent": user_agent},
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        return response.text, response.status_code


def discover_sitemap_urls(
    base_url: str,
    *,
    timeout: int,
    user_agent: str,
    max_urls: int,
    crawl_delay: float,
) -> list[tuple[str, str | None]]:
    """Return list of (url, title) from sitemap(s). One level of sitemap index."""
    candidates = []
    if base_url.lower().endswith(".xml"):
        candidates.append(base_url)
    else:
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        candidates.append(f"{root}/sitemap.xml")

    found: list[tuple[str, str | None]] = []
    seen_sitemaps: set[str] = set()

    for sitemap_url in candidates:
        if len(found) >= max_urls:
            break
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)
        try:
            time.sleep(crawl_delay)
            xml_text, _ = fetch_text(sitemap_url, timeout=timeout, user_agent=user_agent)
            found.extend(_parse_sitemap_xml(xml_text, max_urls - len(found)))
        except Exception as exc:
            logger.warning("Sitemap fetch failed %s: %s", sitemap_url, exc)

    return found[:max_urls]


def _parse_sitemap_xml(xml_text: str, limit: int) -> list[tuple[str, str | None]]:
    results: list[tuple[str, str | None]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return results

    tag = root.tag.lower()
    if tag.endswith("sitemapindex"):
        for loc in root.findall(".//sm:loc", SITEMAP_NS)[:5]:
            if len(results) >= limit:
                break
            child_url = (loc.text or "").strip()
            if child_url:
                try:
                    child_xml, _ = fetch_text(child_url, timeout=30, user_agent="ScrapDiscovery/1.0")
                    results.extend(_parse_sitemap_xml(child_xml, limit - len(results)))
                except Exception:
                    continue
        return results[:limit]

    if tag.endswith("urlset"):
        for url_el in root.findall("sm:url", SITEMAP_NS):
            if len(results) >= limit:
                break
            loc = url_el.find("sm:loc", SITEMAP_NS)
            if loc is not None and loc.text:
                results.append((loc.text.strip(), None))
    return results[:limit]


def discover_html_links(
    base_url: str,
    *,
    timeout: int,
    user_agent: str,
    max_urls: int,
    crawl_delay: float,
    same_host_only: bool = True,
) -> list[tuple[str, str | None]]:
    time.sleep(crawl_delay)
    html, _ = fetch_text(base_url, timeout=timeout, user_agent=user_agent)
    hrefs = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    found: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for href in hrefs:
        if len(found) >= max_urls:
            break
        absolute = resolve_absolute(href, base_url)
        if not absolute:
            continue
        if same_host_only and not same_hostname(absolute, base_url):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        found.append((absolute, None))
    return found
