from urllib.parse import urlparse

from app.parsers.base import BaseParser
from app.parsers.generic_article import GenericArticleParser
from app.parsers.habr_article import HabrArticleParser
from app.parsers.saltpro_article import SaltproArticleParser
from app.parsers.sotbit_article import SotbitArticleParser
from app.parsers.utils import parser_type_for_domain

_REGISTRY: dict[str, BaseParser] = {
    "generic_article": GenericArticleParser(),
    "saltpro_article": SaltproArticleParser(),
    "sotbit_article": SotbitArticleParser(),
    "habr_article": HabrArticleParser(),
    # aliases
    "bitrix_article": SotbitArticleParser(),
}


def resolve_parser_type(source_url: str, parser_type: str | None = None) -> str:
    if parser_type and parser_type != "generic_article" and parser_type in _REGISTRY:
        return parser_type
    domain = urlparse(source_url).netloc.lower().removeprefix("www.")
    return parser_type_for_domain(domain)


def get_parser(parser_type: str) -> BaseParser:
    parser = _REGISTRY.get(parser_type)
    if not parser:
        return _REGISTRY["generic_article"]
    return parser


def get_parser_for_url(source_url: str, parser_type: str | None = None) -> BaseParser:
    resolved = resolve_parser_type(source_url, parser_type)
    return get_parser(resolved)
