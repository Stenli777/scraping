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


QUALITY_REVIEW_V1_SYSTEM = """Ты главный редактор контент-фабрики. Оцени готовую статью после rewrite и SEO.
Отвечай ТОЛЬКО валидным JSON без markdown-обёртки."""

QUALITY_REVIEW_V1_USER = """Оцени качество статьи для публикации как draft. Верни JSON:
- overall_score (integer 0-100)
- readability_score (integer 0-100)
- seo_score (integer 0-100)
- factual_consistency_score (integer 0-100)
- structure_score (integer 0-100)
- usefulness_score (integer 0-100)
- spamminess_score (integer 0-100, выше = больше спама/воды)
- risks (array of strings)
- recommendations (array of strings)
- verdict (string): approved | needs_revision | rejected

{profile_block}

SEO title: {seo_title}
Slug: {slug}
URL: {source_url}

Текст статьи:
---
{content}
---"""


def build_rewrite_messages_from_parts(system: str, user_template: str, ctx: dict) -> list[dict[str, str]]:
    user_content = user_template.format(
        language=ctx.get("language", "ru"),
        profile_block=ctx.get("profile_block", ""),
        source_url=ctx.get("source_url", "не указан"),
        title=ctx.get("title", "Без названия"),
        content=ctx.get("content", ""),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user_content}]


def build_review_messages_from_parts(system: str, user_template: str, ctx: dict) -> list[dict[str, str]]:
    user_content = user_template.format(
        profile_block=ctx.get("profile_block", ""),
        source_url=ctx.get("source_url", "не указан"),
        title=ctx.get("title", "Без названия"),
        content=ctx.get("content", ""),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user_content}]


def build_seo_messages_from_parts(system: str, user_template: str, ctx: dict) -> list[dict[str, str]]:
    user_content = user_template.format(
        profile_block=ctx.get("profile_block", ""),
        source_url=ctx.get("source_url", "не указан"),
        title=ctx.get("title", "Без названия"),
        content=ctx.get("content", ""),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user_content}]


def build_quality_messages_from_parts(system: str, user_template: str, ctx: dict) -> list[dict[str, str]]:
    sys = system or QUALITY_REVIEW_V1_SYSTEM
    tpl = user_template or QUALITY_REVIEW_V1_USER
    user_content = tpl.format(
        profile_block=ctx.get("profile_block", ""),
        seo_title=ctx.get("seo_title", ""),
        slug=ctx.get("slug", ""),
        source_url=ctx.get("source_url", "не указан"),
        content=ctx.get("content", ""),
    )
    return [{"role": "system", "content": sys}, {"role": "user", "content": user_content}]


TOPIC_CLEANUP_V1_SYSTEM = """Ты аналитик тематики и SEO-стратег для B2B CRM-проектов (Bitrix24, CRM, воронки, автоматизация).
Твоя задача — улучшать темы для SEO и стратегии. Отвечай только валидным JSON без markdown."""

TOPIC_CLEANUP_V1_USER = """Ты получаешь результат детерминированного извлечения тем (deterministic) и контент документа.

Ответ JSON:
- primary_topic (string): главная тема одной фразой
- secondary_topics (array of strings): 2-6 тем, по смыслу дополняющих primary
- keywords (array of strings): 5-10 SEO keywords/phrases
- entities (array of strings): бренды/продукты/терминология
- search_intent (string): informational|commercial|transactional|comparison|navigation|unknown
- relevance_score (integer 0-100)
- project_fit (string): crmflow24 или unknown
- rejected_terms (array of strings): отклоненные термины
- warnings (array of strings)
- strategy_allowed (boolean): false для smoke/test/internal/placeholder
- strategy_block_reason (string|null): smoke_test|internal_test|low_relevance|blocked_topic|low_quality|missing_rewrite|unknown

Правила:
- Не добавляй внешние ссылки и markdown.
- Если title/content содержат smoke test, тестовый, пример, mock, placeholder, debug — strategy_allowed=false, strategy_block_reason=smoke_test или internal_test.
- Если статья не про CRM/воронки/автоматизацию — strategy_allowed=false.
- JSON only.

{profile_block}
Title: {title}
SEO title: {seo_title}
SEO description: {seo_description}
Tags: {tags}
Content excerpt:
---
{content_excerpt}
---

Deterministic extraction:
{deterministic_json}

Already rejected terms:
{rejected_terms}
"""


def build_topic_cleanup_messages(ctx: dict) -> list[dict[str, str]]:
    user = TOPIC_CLEANUP_V1_USER.format_map({
        "profile_block": ctx.get("profile_block", ""),
        "title": ctx.get("title", ""),
        "seo_title": ctx.get("seo_title", ""),
        "seo_description": ctx.get("seo_description", ""),
        "tags": ctx.get("tags", ""),
        "content_excerpt": ctx.get("content_excerpt", ""),
        "deterministic_json": ctx.get("deterministic_json", "{}"),
        "rejected_terms": ctx.get("rejected_terms", "[]"),
    })
    return [
        {"role": "system", "content": TOPIC_CLEANUP_V1_SYSTEM},
        {"role": "user", "content": user},
    ]
