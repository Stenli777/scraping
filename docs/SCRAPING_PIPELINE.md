# Scraping pipeline

## Статусы

`queued` → `fetching` → `parsing` → `cleaning` → `rewriting` → `saving` → `done` | `error`

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
