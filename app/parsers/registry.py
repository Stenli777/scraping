from app.core.enums import ParserType
from app.parsers.base import BaseParser
from app.parsers.generic_article import GenericArticleParser

_REGISTRY: dict[str, BaseParser] = {
    ParserType.GENERIC_ARTICLE.value: GenericArticleParser(),
}


def get_parser(parser_type: str) -> BaseParser:
    parser = _REGISTRY.get(parser_type)
    if not parser:
        raise ValueError(f"Unknown parser_type: {parser_type}")
    return parser
