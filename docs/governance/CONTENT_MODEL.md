# Content Model — Scrap

Модель данных контента: **Current** (production pipeline) и **Target** (Stage 5 — future). Термины согласованы с `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/CRMFLOW24_INTEGRATION.md`.

## Current — scraped pipeline

Цепочка (логическая, не все шаги обязательны для каждого документа):

```text
source URL
  → scraping_task (queued … done | error | failed_retryable)
  → parsed_document (clean_text, raw artifacts, hashes, SEO/rewrite fields)
  → document_revision (immutable snapshots: rewrite / seo / quality / publish)
  → release_candidate (binds document_revision_id + publish target + QA)
  → publish_run
  → publication_record
```

### Сущности (кратко)

| Сущность | Роль |
|----------|------|
| `sources` | Уникальный URL источника |
| `scraping_tasks` | Очередь и статус pipeline |
| `parsed_documents` | Рабочий документ после parse/clean/rewrite |
| `document_revisions` | **Immutable** снимок версии контента |
| `release_candidates` | Кандидат на publish; привязан к **одной** revision |
| `publish_runs` | Попытка отправки draft; `document_revision_id`, опционально `release_candidate_id` |
| `publication_records` | Факт успешной доставки draft во внешнюю систему |

Параллельные слои (не заменяют цепочку):

- editorial (`editorial_status`, operator approval);
- quality (`content_quality_scores`, verdict);
- strategy (topics, campaigns, clusters — deterministic-first);
- canonical / similarity / lineage (warnings, не auto-delete);
- draft review после publish (`draft_review_*` на RC/publication);
- public confirmation (4Q): Scrap фиксирует **видимость** public URL, не публикует пост.

## Target — Stage 5 Content Studio Automation

**Не реализован.** Целевая цепочка для **generated** контента:

```text
content_topic_batch
  → content_topic
  → content_brief
  → generated_document | parsed_document (source_type=generated)
  → document_revision
  → release_candidate
  → publish_run
  → publication_record
```

| | |
|---|---|
| **Target** | `source_type=generated` отличает происхождение от scrape. |
| **Target** | Brief обязателен как gate перед article_writer (AUTOMATION_POLICY). |
| **Target** | Те же RC + publish gates, что и для scraped (PUBLISH_POLICY). |

Scraped и generated сходятся на **revision → RC → publish**; различается только upstream provenance (см. PROVENANCE_MODEL).

## Source of truth

| Данные | Правило |
|--------|---------|
| Raw scraped HTML / исходный fetch | **Immutable** после сохранения; не перезаписывать «тихо» при rerun rewrite |
| `clean_text` (после clean) | Source для rewrite; rerun rewrite **не** повторяет fetch без явной задачи |
| `document_revision` | **Immutable**; новая версия = новая строка |
| `release_candidate` | Привязан к `document_revision_id`; смена revision → **новый** candidate |
| `publication_record` | Запись о доставке **draft**; **≠** public publish без operator confirmation в CRMFlow24 |
| Generated article (Target) | Должен иметь полный provenance (topic, brief, llm_runs, prompts) |

## Статусы и gates (Current)

- Pipeline task: `queued` → … → `done` / `error` / `failed_retryable` (см. SCRAPING_PIPELINE).
- Quality verdict: `approved` | `needs_revision` | `rejected` — не обходить automation без force + audit.
- Editorial: operator approval отдельно от LLM quality.
- RC QA: deterministic score 0–100; не ML (ARCHITECTURE §4L).

## Forbidden

| | |
|---|---|
| **Forbidden** | Считать `publication_record` эквивалентом «статья в блоге live». |
| **Forbidden** | Редактировать старую `document_revision` in-place. |
| **Forbidden** | Publish RC без привязки к revision (обход snapshot). |
| **Forbidden** | Утверждать, что Stage 5 tables/flows уже в production. |

## Required

| | |
|---|---|
| **Required** | При rerun rewrite/SEO/quality — новая revision или явная audit-запись (HUMAN_OVERRIDE_POLICY). |
| **Required** | Production publish path через release candidate (PUBLISH_POLICY). |
| **Required** | `content_hash` + `source_url` для дедупа scraped (DATABASE). |

## Связь с media (Current)

```text
document → media_prompt (LLM) → media_job → provider → media_asset
```

Media не блокирует publish по умолчанию; readiness warning если нет approved preview (ARCHITECTURE).

## Открытые вопросы

- Имя и схема таблиц Stage 5 (`content_topic_batch` vs существующие campaigns/clusters).
- Один `parsed_documents` для scraped+generated или отдельная таблица generated.
- Versioning brief при перегенерации outline/article.
