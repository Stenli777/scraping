import logging

import httpx

from app.core.config import get_settings
from app.rewriters.base import BaseRewriter

logger = logging.getLogger(__name__)


class CLIProxyRewriter(BaseRewriter):
    """OpenAI-compatible rewrite via CLIProxyAPI (stage 2+)."""

    provider_name = "cliproxy"

    def rewrite(self, text: str, metadata: dict | None = None) -> str:
        settings = get_settings()
        if not settings.cliproxyapi_base_url or not settings.cliproxyapi_api_key:
            raise RuntimeError("CLIProxyAPI is not configured")

        prompt = (
            "Перепиши текст статьи для публикации на сайте. "
            "Сохрани смысл, улучши структуру, без выдуманных фактов.\n\n"
            f"{text}"
        )
        url = f"{settings.cliproxyapi_base_url.rstrip('/')}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.cliproxyapi_api_key}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=120) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]
