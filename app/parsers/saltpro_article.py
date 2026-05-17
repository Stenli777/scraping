from app.parsers.base import BaseParser, ParseResult
from app.parsers.utils import parse_article_block


class SaltproArticleParser(BaseParser):
    parser_type = "saltpro_article"

    def parse(self, url: str, html: str) -> ParseResult:
        title, raw_text, clean_text, metadata = parse_article_block(
            url,
            html,
            self.parser_type,
            content_selectors=[
                "article",
                ".article-detail",
                ".blog-article",
                ".news-detail",
                "main .content",
                "main",
            ],
            date_selector="time",
            tag_selector=".tags a, .article-tags a",
        )
        return ParseResult(
            title=title,
            raw_html=html,
            raw_text=raw_text,
            clean_text=clean_text,
            metadata=metadata,
        )
