from app.parsers.base import BaseParser, ParseResult
from app.parsers.utils import parse_article_block


class HabrArticleParser(BaseParser):
    parser_type = "habr_article"

    def parse(self, url: str, html: str) -> ParseResult:
        title, raw_text, clean_text, metadata = parse_article_block(
            url,
            html,
            self.parser_type,
            content_selectors=[
                ".article-formatted-body",
                ".tm-article-body",
                "article",
            ],
            author_selector=".tm-user-info__username, .author-name",
            date_selector="time",
            tag_selector=".tm-tags-list__link, .tags a",
        )
        return ParseResult(
            title=title,
            raw_html=html,
            raw_text=raw_text,
            clean_text=clean_text,
            metadata=metadata,
        )
