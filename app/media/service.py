from app.core.config import get_settings
from app.media.base import BaseMediaProvider
from app.media.exceptions import MediaProviderError
from app.media.placeholder_provider import PlaceholderMediaProvider

_PROVIDERS: dict[str, type[BaseMediaProvider]] = {
    "placeholder": PlaceholderMediaProvider,
}


def get_media_provider(name: str | None = None) -> BaseMediaProvider:
    settings = get_settings()
    key = (name or settings.media_provider or "placeholder").strip().lower()
    cls = _PROVIDERS.get(key)
    if not cls:
        raise MediaProviderError(f"Unknown media provider: {key}")
    return cls()


class MediaProviderService:
    def __init__(self, provider: BaseMediaProvider | None = None) -> None:
        self._provider = provider or get_media_provider()

    def generate_preview(self, **kwargs):
        return self._provider.generate_preview(**kwargs)
