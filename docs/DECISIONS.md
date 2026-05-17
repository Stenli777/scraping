# Архитектурные решения (ADR)

## ADR-001: FastAPI + Jinja admin

**Решение:** один процесс FastAPI с Jinja2-шаблонами для MVP.

## ADR-002: DB-polling worker

**Решение:** worker читает `scraping_tasks` со статусом `queued`.

## ADR-003: Scrapling + trafilatura fallback

**Решение:** fetch через Scrapling `Fetcher`, при ошибке — httpx; clean через trafilatura + selectors.

## ADR-004: Mock rewriter на этапе 1

**Решение:** `REWRITER_PROVIDER=mock` по умолчанию.

## ADR-005: Дедупликация content_hash

**Решение:** проверка hash; повтор того же URL — `done` без нового документа (лог с `document_id`).

## ADR-006: Backups на диск

**Решение:** `storage/backups/YYYY/MM/DD/<task_id>/`.

## ADR-007: Domain-based parsers (2026-05-17)

**Решение:** `saltpro_article`, `sotbit_article`, `habr_article` + `resolve_parser_type()` по домену.

**Причина:** generic parser оставлял шум в raw_text; domain selectors улучшают clean_text и metadata (`word_count`, `parser_name`).
