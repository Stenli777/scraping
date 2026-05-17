# Scraping pipeline

## Статусы

`queued` → `fetching` → `parsing` → `cleaning` → `rewriting` → `saving` → `done` | `error`

## Парсеры

| parser_type | Статус |
|-------------|--------|
| `generic_article` | реализован |
| `bitrix_article` | план |
| `habr_article` | план |

## Тестовые URL

1. https://saltpro.ru/articles/bitriks24-kedo-reytinge-cnewsmarket-2025/
2. https://saltpro.ru/articles/bitriks24-vibecode-reliz-2026/
3. https://saltpro.ru/articles/nalogovaya-reforma-2026-kak-perestroit-biznes-s-bitriks24/
4. https://www.sotbit.ru/info/bitrix24/nastroyka-crm-bitriks24.html
5. https://habr.com/ru/companies/bitrix/articles/1031736/

## Fetch

`app/parsers/fetcher.py` — Scrapling `Fetcher`, fallback httpx.

## Clean

trafilatura + fallback на нормализованный plain text.
