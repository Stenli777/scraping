# Provenance Model — Scrap

Цепочка происхождения контента и минимальный **audit trail**. Дополняет CONTENT_MODEL и AI_POLICY.

## Зачем

Оператор и аудит должны ответить: **откуда текст/медиа**, **какой промпт/модель**, **какая revision ушла в publish**, без смешения scraped raw и generated draft.

## Scraped content

| Поле / артефакт | Назначение |
|-----------------|------------|
| `source_url` | Первичный URL |
| `sources` / directory | Каталог, discovery context |
| `raw_html` / fetch artifact | Immutable source material |
| `clean_text` | После parse/clean |
| `content_hash` | Дедуп с `source_url` |
| `parser` / `parser_type` | Как извлекли структуру |
| `scraping_task.id` | Задача pipeline |
| `pipeline_events` | Стадии fetch/parse/clean |

**Required:** не перезаписывать raw без новой задачи/scrape; hash меняется → новый документ или явная политика duplicate.

## Rewritten content

| Связь | Назначение |
|-------|------------|
| Source document | `parsed_document` до rewrite |
| `clean_text` input | Вход rewriter |
| Prompt | `prompt_templates` key + version в `llm_runs.prompt_template` |
| Model | alias, upstream, fallback в `llm_runs` |
| `llm_run.id` | Audit одного вызова |
| `document_revision` | Immutable snapshot после rewrite/seo/quality |

Rerun rewrite → **новый** `llm_run` + **новая** revision (или audit entry) — HUMAN_OVERRIDE_POLICY.

## Generated content (Target — Stage 5)

**Не в production.** Минимальная целевая цепочка:

| Узел | Provenance fields |
|------|-------------------|
| `content_topic_batch` | project, operator, limits, created_at |
| `content_topic` | keyword/intent, batch_id, strategy link — **`topic_id`** |
| `content_brief` | research context, sources cited, brief prompt version — **`brief_id`** |
| `outline` | **`outline_planner` `llm_run`**, structure JSON |
| `article draft` | **`article_writer` `llm_run`**, models, temperature policy |
| `parsed_document` / generated document | **`source_type=generated`** (обязательно) |

### Required (Target)

| | |
|---|---|
| **Required** | Generated article/document хранит **`source_type=generated`**. |
| **Required** | Связи: **`topic_id`**, **`brief_id`**, **`outline` llm_run**, **`article_writer` llm_run**. |
| **Forbidden** | Generated document без `brief_id` / `topic_id` в auto pipeline. |
| **Forbidden** | Generated publish payload **не должен** выдавать несуществующий scraped `source_url` (не притворяться scrape). |

### Publish payload (Target)

| | |
|---|---|
| **Target** | `article_v2` eventually включает **`source.type`**: `generated` \| `scraped` \| `manual`. |
| **Current** | `article_v2.source` ориентирован на scraped (`source_url`, `source_domain`, …) — для generated нужно расширение контракта, не подстановка фиктивного URL. |
| **Required** | При `source.type=generated` — provenance из topic/brief/llm_runs, не из `scraping_task`. |

## Media

| Узел | Provenance |
|------|------------|
| `media_prompt` | LLM run, prompt version |
| `media_job` | provider, status |
| `media_asset` | file path, approval state |
| Publish payload | `media.preview` in article_v2 |

**Current:** local storage `storage/media/`; не в Git.

## Publish

| Узел | Provenance |
|------|------------|
| `release_candidate` | `document_revision_id`, QA snapshot, target id |
| `publish_run` | revision_id, `release_candidate_id`, payload_version, dry_run, force |
| `publication_record` | external draft id, draft_url, remote_status |
| Payload | `source`, `editorial`, `publication` blocks in article_v2 |

**Required:** publish_run всегда ссылается на revision, отправленную в payload (`revision_id` in article_v2).

## Lineage и canonical (Current)

- `rewrite_lineage` — immutable chain source → rewrite → revision.
- Canonical groups / similarity links — **warnings**, provenance для duplicate/cannibalization, не удаление контента.

## Минимальный audit trail

Для любого production-значимого действия должно быть возможно восстановить:

1. **Who** — operator (admin session) или `automation_run` / worker job id.  
2. **What** — entity ids: document, revision, RC, publish_run.  
3. **When** — timestamps в DB.  
4. **Why** — для force: reason + `force_used`; для automation: rule id + logs_json.  
5. **How (AI)** — `llm_runs` + prompt key:version + model alias.

### Таблицы / события (Current)

| Механизм | Содержит |
|----------|----------|
| `llm_runs` | LLM вызовы |
| `pipeline_events` | Стадии pipeline |
| `document_revisions` | Snapshots |
| `automation_runs` | Automation audit |
| `publish_runs` | Publish attempts |
| `hermes_runs` | Optional Hermes (не blocking) |
| `metadata_json` (document/task) | topic extractions, enrichment merge audit |

**Forbidden:** LLM или publish без возможности связать с document/revision.

## Retention

| | |
|---|---|
| **Current** | Backups JSON/Markdown в `storage/backups/` при ключевых rerun/publish. |
| **Required** | Не коммитить backups и media в Git. |
| **Open** | Срок хранения raw_html vs cost (ops decision). |

## Открытые вопросы

- Единый `provenance_json` на revision vs разнесённые FK.
- Точная схема `article_v2.source` для `generated` (поля vs nested `provenance`).
- WORM / external audit store для compliance.
