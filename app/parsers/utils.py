import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import trafilatura

from app.services.hashing import content_hash

logger = logging.getLogger(__name__)

NOISE_PATTERNS = (
    r"^(поделиться|share|читать также|related|комментари|cookie|©|copyright)",
    r"^(главная|home|меню|menu|навигация)",
    r"^(войти|login|регистрация|subscribe)",
)


def domain_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


def parser_type_for_domain(domain: str) -> str:
    if domain == "saltpro.ru":
        return "saltpro_article"
    if domain in ("sotbit.ru", "www.sotbit.ru"):
        return "sotbit_article"
    if domain == "habr.com":
        return "habr_article"
    return "generic_article"


def strip_noise_lines(text: str) -> str:
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) < 3:
            continue
        lower = s.lower()
        if any(re.match(p, lower) for p in NOISE_PATTERNS):
            continue
        if lower.count("|") > 3 and len(s) < 120:
            continue
        lines.append(s)
    return "\n\n".join(lines)


def extract_title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def extract_with_trafilatura(url: str, html: str) -> str | None:
    try:
        extracted = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        if extracted and len(extracted.strip()) > 80:
            return extracted.strip()
    except Exception as exc:
        logger.warning("trafilatura failed for %s: %s", url, exc)
    return None


def soup_from_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer", "header"]):
        tag.decompose()
    return soup


def text_from_selectors(soup: BeautifulSoup, selectors: list[str]) -> str | None:
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        text = node.get_text("\n", strip=True)
        if text and len(text) > 120:
            return strip_noise_lines(text)
    return None


def meta_content(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            val = tag.get("content")
            return val.strip() if isinstance(val, str) else str(val).strip()
    return None


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def build_metadata(
    *,
    url: str,
    parser_name: str,
    title: str,
    clean_text: str,
    author: str | None = None,
    published_at: str | None = None,
    tags: list[str] | None = None,
    warnings: list[str] | None = None,
    extra: dict | None = None,
) -> dict:
    meta = {
        "domain": domain_from_url(url),
        "parser_name": parser_name,
        "extracted_title": title,
        "title": title,
        "url": url,
        "content_hash": content_hash(clean_text),
        "word_count": word_count(clean_text),
        "extraction_warnings": warnings or [],
    }
    if author:
        meta["detected_author"] = author
    if published_at:
        meta["published_at"] = published_at
    if tags:
        meta["tags"] = tags
    if extra:
        meta.update(extra)
    return meta


def parse_article_block(
    url: str,
    html: str,
    parser_name: str,
    content_selectors: list[str],
    *,
    author_selector: str | None = None,
    date_selector: str | None = None,
    tag_selector: str | None = None,
) -> tuple[str, str, str, dict]:
    """Returns title, raw_text, clean_text, metadata."""
    soup = soup_from_html(html)
    title = extract_title(soup)
    raw_text = soup.get_text("\n", strip=True)
    warnings: list[str] = []

    clean_text = text_from_selectors(soup, content_selectors)
    if not clean_text:
        clean_text = extract_with_trafilatura(url, html)
    if not clean_text:
        clean_text = strip_noise_lines(raw_text)
        warnings.append("fallback_noise_strip")

    author = None
    if author_selector:
        node = soup.select_one(author_selector)
        if node:
            author = node.get_text(strip=True)

    published_at = meta_content(soup, "article:published_time", "pubdate", "date")
    if not published_at and date_selector:
        node = soup.select_one(date_selector)
        if node:
            published_at = node.get("datetime") or node.get_text(strip=True)

    tags: list[str] = []
    if tag_selector:
        tags = [t.get_text(strip=True) for t in soup.select(tag_selector)[:10] if t.get_text(strip=True)]

    metadata = build_metadata(
        url=url,
        parser_name=parser_name,
        title=title,
        clean_text=clean_text,
        author=author,
        published_at=published_at,
        tags=tags or None,
        warnings=warnings,
    )
    return title, raw_text, clean_text, metadata
