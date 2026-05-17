from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ParseResult:
    title: str
    raw_html: str
    raw_text: str
    clean_text: str
    metadata: dict


class BaseParser(ABC):
    parser_type: str

    @abstractmethod
    def parse(self, url: str, html: str) -> ParseResult:
        raise NotImplementedError
