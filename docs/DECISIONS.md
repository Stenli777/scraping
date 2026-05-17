# Архитектурные решения (ADR)

## ADR-001: FastAPI + Jinja admin

**Решение:** один процесс FastAPI с Jinja2-шаблонами для MVP.

**Причина:** быстрее production MVP, один systemd unit, без отдельного frontend build.

## ADR-002: DB-polling worker

**Решение:** worker читает `scraping_tasks` со статусом `queued`.

**Причина:** на сервере нет Redis; pipeline изолирован в `PipelineService`, позже можно подключить ARQ.

## ADR-003: Scrapling + trafilatura fallback

**Решение:** fetch через Scrapling `Fetcher`, при ошибке — httpx; clean через trafilatura.

## ADR-004: Mock rewriter на этапе 1

**Решение:** `REWRITER_PROVIDER=mock` по умолчанию.

**Причина:** end-to-end pipeline без внешних API; интерфейсы для CLIProxy/LM Studio готовы.

## ADR-005: Дубли по content_hash + source_url

**Решение:** перед сохранением проверка hash; повторный scrape той же страницы с тем же hash → error.

## ADR-006: Backups на диск

**Решение:** после успешной задачи — `storage/backups/YYYY/MM/DD/<task_id>/`.
