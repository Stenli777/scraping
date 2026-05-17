from abc import ABC, abstractmethod


class BaseRewriter(ABC):
    provider_name: str

    @abstractmethod
    def rewrite(self, text: str, metadata: dict | None = None) -> str:
        raise NotImplementedError
