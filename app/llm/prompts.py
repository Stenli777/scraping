"""Code-based prompt templates. TODO: migrate to prompt_templates DB table."""

from app.llm.schemas import ReviewRequest, RewriteRequest, SeoEnrichRequest

REWRITE_ARTICLE_V1 = "rewrite_article_v1"
REVIEW_ARTICLE_V1 = "review_article_v1"
SEO_ENRICH_V1 = "seo_enrich_v1"

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

{profile_block}

Источник: {source_url}
Заголовок источника: {title}

Исходный текст:
---
{content}
---

Верни только текст статьи в Markdown, без пояснений."""

REVIEW_ARTICLE_V1_SYSTEM = """Ты редактор контент-фабрики. Оцени материал для публикации.
Отвечай ТОЛЬКО валидным JSON без markdown-обёртки."""

REVIEW_ARTICLE_V1_USER = """Проанализируй статью и верни JSON с полями:
- take (boolean): брать статью в работу или нет
- score (integer 0-100): релевантность и качество для целевого проекта
- reason (string): краткое обоснование
- target_project (string|null): slug проекта, например crmflow24
- recommended_angle (string|null): рекомендуемый угол подачи
- content_type (string|null): news, guide, case, opinion, other
- risks (array of strings): риски публикации

{profile_block}

URL: {source_url}
Заголовок: {title}

Текст:
---
{content}
---"""

SEO_ENRICH_V1_SYSTEM = """Ты SEO-редактор для B2B контента (CRM, Bitrix24).
Генерируй метаданные без keyword stuffing — readable, business-oriented, human-friendly.
Отвечай ТОЛЬКО валидным JSON."""

SEO_ENRICH_V1_USER = """Сгенерируй SEO-метаданные для статьи. Верни JSON:
- seo_title (string, до 70 символов)
- seo_description (string, до 160 символов)
- h1 (string)
- slug (string, латиница, kebab-case)
- excerpt (string, 1-2 предложения)
- tags (array of strings, 3-8 тегов)
- faq (array of objects with question, answer — 2-4 пары)
- suggested_category (string)

{profile_block}

URL: {source_url}
Заголовок: {title}

Текст статьи:
---
{content}
---"""


def _profile_block(profile_context: str | None) -> str:
    if not profile_context or not profile_context.strip():
        return ""
    return f"Профиль проекта:\n{profile_context.strip()}\n"


def build_rewrite_messages(
    request: RewriteRequest, profile_context: str | None = None
) -> list[dict[str, str]]:
    ctx = profile_context or request.metadata.get("profile_context")
    user_content = REWRITE_ARTICLE_V1_USER.format(
        language=request.language,
        profile_block=_profile_block(ctx),
        source_url=request.source_url or "не указан",
        title=request.title or "Без названия",
        content=request.content.strip(),
    )
    return [
        {"role": "system", "content": REWRITE_ARTICLE_V1_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def build_review_messages(request: ReviewRequest) -> list[dict[str, str]]:
    ctx = request.profile_context or request.metadata.get("profile_context")
    user_content = REVIEW_ARTICLE_V1_USER.format(
        profile_block=_profile_block(ctx),
        source_url=request.source_url or "не указан",
        title=request.title or "Без названия",
        content=request.content.strip()[:12000],
    )
    return [
        {"role": "system", "content": REVIEW_ARTICLE_V1_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def build_seo_messages(request: SeoEnrichRequest) -> list[dict[str, str]]:
    ctx = request.profile_context or request.metadata.get("profile_context")
    user_content = SEO_ENRICH_V1_USER.format(
        profile_block=_profile_block(ctx),
        source_url=request.source_url or "не указан",
        title=request.title or "Без названия",
        content=request.content.strip()[:12000],
    )
    return [
        {"role": "system", "content": SEO_ENRICH_V1_SYSTEM},
        {"role": "user", "content": user_content},
    ]
