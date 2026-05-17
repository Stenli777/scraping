import logging
import re

from bs4 import BeautifulSoup
import trafilatura

from app.parsers.base import BaseParser, ParseResult
from app.services.hashing import content_hash

logger = logging.getLogger(__name__)


class GenericArticleParser(BaseParser):
    parser_type = "generic_article"

    def parse(self, url: str, html: str) -> ParseResult:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()

        title = self._extract_title(soup)
        raw_text = soup.get_text("\n", strip=True)
        clean_text = self._extract_clean_text(url, html) or self._fallback_clean(raw_text)

        metadata = {
            "title": title,
            "url": url,
            "content_hash": content_hash(clean_text),
            "parser": self.parser_type,
        }
        return ParseResult(
            title=title,
            raw_html=html,
            raw_text=raw_text,
            clean_text=clean_text,
            metadata=metadata,
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        h1 = soup.find("h1")
        return h1.get_text(strip=True) if h1 else ""

    def _extract_clean_text(self, url: str, html: str) -> str | None:
        try:
            extracted = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                favor_precision=True,
            )
            if extracted and len(extracted.strip()) > 100:
                return extracted.strip()
        except Exception as exc:
            logger.warning("trafilatura extract failed: %s", exc)
        return None

    def _fallback_clean(self, raw_text: str) -> str:
        lines = [line.strip() for line in raw_text.splitlines()]
        lines = [line for line in lines if line and len(line) > 2]
        collapsed = "\n\n".join(lines)
        return re.sub(r"\n{3,}", "\n\n", collapsed).strip()
