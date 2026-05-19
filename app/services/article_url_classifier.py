"""Article-only URL classifier for trusted source intake."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ArticleClassification:
    article_likelihood: int
    is_article: bool
    reasons: list[str]


AUTOBIT24_POSITIVE = re.compile(
    r"^https?://(www\.)?autobit24\.ru/blog/[^/?#]+$",
    re.I,
)

NEGATIVE_PATH_FRAGMENTS = (
    "/tag/",
    "/tags/",
    "/category/",
    "/categories/",
    "/author/",
    "/users/",
    "/search",
    "/page/",
    "/feed",
    "/rss",
    "#comments",
    "/wp-content/",
    "/wp-json/",
)

NEGATIVE_EXACT_SUFFIXES = (
    "/blog",
    "/blog/",
)


def classify_article_url(url: str, *, host_hint: str | None = None) -> ArticleClassification:
    """Return article_likelihood 0-100 and is_article for a URL."""
    reasons: list[str] = []
    parsed = urlparse(url.strip())
    host = (parsed.hostname or host_hint or "").lower()
    path = (parsed.path or "").lower()
    full = url.lower()

    if not host:
        return ArticleClassification(0, False, ["missing_host"])

    for frag in NEGATIVE_PATH_FRAGMENTS:
        if frag in full:
            return ArticleClassification(5, False, [f"negative_path:{frag.strip('/')}"])

    if any(full.rstrip("/").endswith(s.rstrip("/")) for s in NEGATIVE_EXACT_SUFFIXES):
        return ArticleClassification(10, False, ["listing_page"])

    if "?p=" in full or "replytocom=" in full:
        return ArticleClassification(5, False, ["query_junk"])

    score = 40
    parts = [p for p in path.strip("/").split("/") if p]

    if host.endswith("autobit24.ru"):
        if AUTOBIT24_POSITIVE.match(url.strip()):
            slug = parts[-1] if len(parts) >= 2 and parts[0] == "blog" else ""
            if slug and slug not in ("page", "category", "tag", "author"):
                score = 92
                reasons.append("autobit24_blog_slug")
            else:
                score = 25
                reasons.append("autobit24_weak_slug")
        elif len(parts) >= 2 and parts[0] == "blog":
            score = 75
            reasons.append("autobit24_blog_path")
        else:
            score = 20
            reasons.append("autobit24_non_article_path")
    elif "/blog/" in path or "/articles/" in path or "/info/" in path:
        if len(parts) >= 2:
            score = 70
            reasons.append("generic_blog_path")
        else:
            score = 30
            reasons.append("shallow_path")
    elif "/ru/articles/" in path or "/companies/" in path and "/articles/" in path:
        score = 85
        reasons.append("habr_article_path")
    else:
        score = 35
        reasons.append("unknown_pattern")

    is_article = score >= 65
    return ArticleClassification(score, is_article, reasons)
