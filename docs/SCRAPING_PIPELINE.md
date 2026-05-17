# Scraping pipeline

## Статусы

`queued` → `fetching` → `parsing` → `cleaning` → `reviewing` (optional) → `rewriting` → `seo_enriching` (optional) → `saving` → `done`

При ошибке rewrite (CLIProxy недоступен и т.п.): `failed_retryable` — raw/clean сохранены, `rewritten_text` пустой или прежний.

Критическая ошибка fetch/parse: `error`.

## Rewrite providers

| `REWRITER_PROVIDER` | Поведение |
|---------------------|-----------|
| `mock` | Dev/fallback: префикс `[MOCK REWRITE]` |
| `cliproxy` | LLM layer → CLIProxyAPI OpenAI `/v1/chat/completions` |

Env (см. `.env.example`):

- `REWRITE_MODEL_ALIAS=local/rewrite-main` — обязателен для cliproxy
- `REVIEW_MODEL_ALIAS`, `SEO_MODEL_ALIAS` — для будущих стадий review/SEO
- `CLIPROXYAPI_BASE_URL`, `CLIPROXYAPI_API_KEY`

Prompt template: `rewrite_article_v1` (`app/llm/prompts.py`). TODO: перенос в DB `prompt_templates`.

### Production switch

```bash
# включить CLIProxy rewrite
REWRITER_PROVIDER=cliproxy
REWRITE_MODEL_ALIAS=local/rewrite-main
CLIPROXYAPI_BASE_URL=http://127.0.0.1:8317
# systemctl restart scrap-api scrap-worker

# откат на mock
REWRITER_PROVIDER=mock
```

После смены env: `systemctl restart scrap-api scrap-worker`.

### Feature flags

| Flag | Default | Эффект |
|------|---------|--------|
| `ENABLE_LLM_REVIEW` | true | Стадия review после clean |
| `ENABLE_SEO_ENRICH` | true | SEO metadata после rewrite |
| `ENABLE_PROJECT_PROFILES` | true | Профиль проекта в промптах |

### Manual review / SEO

- `POST /api/documents/{id}/run-review` — без повторного fetch
- `POST /api/documents/{id}/run-seo` — по rewritten_text или clean_text

### Rerun rewrite

Без повторного fetch: admin кнопка или `POST /api/documents/{id}/rerun-rewrite`.

## Выбор парсера (по домену)

| Домен | parser_type |
|-------|-------------|
| `saltpro.ru` | `saltpro_article` |
| `sotbit.ru` | `sotbit_article` |
| `habr.com` | `habr_article` |
| прочие | `generic_article` |

Роутинг: `app/parsers/registry.py` → `resolve_parser_type()`.

## Парсеры

| Файл | Назначение |
|------|------------|
| `generic_article.py` | fallback |
| `saltpro_article.py` | saltpro.ru |
| `sotbit_article.py` | sotbit.ru |
| `habr_article.py` | habr.com |
| `utils.py` | общая логика extract/clean/metadata |

## Тестовые URL (прогон 2026-05-17)

| URL | Task | Parser | Статус |
|-----|------|--------|--------|
| saltpro …kedo-reytinge… | #1 | generic_article | done (doc #1) |
| saltpro …kedo… (повтор) | #2 | saltpro_article | duplicate → skip (doc #1) |
| saltpro …vibecode… | #3 | saltpro_article | done (doc #2) |
| saltpro …nalogovaya… | #4 | saltpro_article | done (doc #3) |
| sotbit …nastroyka-crm… | #5 | sotbit_article | done (doc #4) |
| habr …1031736 | #6 | habr_article | done (doc #5) |

## Fetch

`app/parsers/fetcher.py` — Scrapling `Fetcher`, fallback httpx.

## Дедупликация

`content_hash` + `source_url`. Повтор того же URL с тем же hash — задача завершается без ошибки (ссылка на существующий документ в логах).

## Backups

`storage/backups/YYYY/MM/DD/<task_id>/` — raw.html, raw.txt, clean.md, rewritten.md, metadata.json
