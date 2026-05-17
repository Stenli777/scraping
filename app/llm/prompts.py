"""Code-based prompt templates. TODO: migrate to prompt_templates DB table."""

from app.llm.schemas import RewriteRequest

REWRITE_ARTICLE_V1 = "rewrite_article_v1"

REWRITE_ARTICLE_V1_SYSTEM = """Ты редактор контента для публикации на сайте.
Пиши на русском языке в формате Markdown.
Не добавляй изображения и не предлагай автопубликацию."""

REWRITE_ARTICLE_V1_USER = """Перепиши исходный материал в новую оригинальную статью.

Требования:
- НЕ делай синонимайзинг и не перефразируй предложение за предложением.
- Напиши новую оригинальную статью на основе фактов из источника.
- НЕ копируй структуру источника дословно (заголовки, порядок блоков можно менять).
- Сохраняй фактическую точность — не выдумывай факты, цифры, имена, даты.
- Если факта нет в источнике — не добавляй его.
- Формат: Markdown с заголовком H1 и логичными H2/H3.
- Язык: {language}.

Источник: {source_url}
Заголовок источника: {title}

Исходный текст:
---
{content}
---

Верни только текст статьи в Markdown, без пояснений."""


def build_rewrite_messages(request: RewriteRequest) -> list[dict[str, str]]:
    user_content = REWRITE_ARTICLE_V1_USER.format(
        language=request.language,
        source_url=request.source_url or "не указан",
        title=request.title or "Без названия",
        content=request.content.strip(),
    )
    return [
        {"role": "system", "content": REWRITE_ARTICLE_V1_SYSTEM},
        {"role": "user", "content": user_content},
    ]
