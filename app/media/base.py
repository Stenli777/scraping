from abc import ABC, abstractmethod

from app.media.schemas import MediaGenerateResult


class BaseMediaProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate_preview(
        self,
        *,
        prompt: str,
        alt_text: str,
        caption: str,
        document_id: int,
        negative_prompt: str | None = None,
    ) -> MediaGenerateResult:
        ...
