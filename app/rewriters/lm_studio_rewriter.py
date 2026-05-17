import httpx

from app.core.config import get_settings
from app.rewriters.base import BaseRewriter


class LMStudioRewriter(BaseRewriter):
    provider_name = "lm_studio"

    def rewrite(self, text: str, metadata: dict | None = None) -> str:
        settings = get_settings()
        url = f"{settings.lm_studio_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": "local-model",
            "messages": [
                {
                    "role": "user",
                    "content": f"Перепиши текст статьи:\n\n{text}",
                }
            ],
        }
        with httpx.Client(timeout=180) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]
