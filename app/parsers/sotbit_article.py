from app.parsers.base import BaseParser, ParseResult
from app.parsers.utils import parse_article_block


class SotbitArticleParser(BaseParser):
    parser_type = "sotbit_article"

    def parse(self, url: str, html: str) -> ParseResult:
        title, raw_text, clean_text, metadata = parse_article_block(
            url,
            html,
            self.parser_type,
            content_selectors=[
                "article",
                ".article-content",
                ".content-block",
                ".detail-text",
                "main .container",
                "main",
            ],
            author_selector=".author, .article-author",
            date_selector="time, .date",
        )
        return ParseResult(
            title=title,
            raw_html=html,
            raw_text=raw_text,
            clean_text=clean_text,
            metadata=metadata,
        )
