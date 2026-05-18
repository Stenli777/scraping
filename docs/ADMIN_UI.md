# Admin UI

Base: **https://scrap.crmflow24.ru/admin**

| URL | Страница |
|-----|----------|
| `/admin` | Dashboard — ID, URL, статус, парсер, документ |
| `/admin/tasks/new` | Добавить URL (парсер подбирается по домену) |
| `/admin/tasks/{id}` | Статус, парсер, тайминги, ошибки, логи с payload |
| `/admin/documents/{id}` | clean / rewritten / raw, metadata, export |
| `/admin/settings` | env flags (без секретов) |
| `/admin/llm-runs` | Аудит LLM: task_id, project_id, alias, upstream, tokens, latency, success, fallback |
| `/admin/pipeline-events` | События pipeline по стадиям |
| `/admin/llm/smoke` | Ручной smoke test LLM |
| `/admin/projects` | Список проектов |
| `/admin/projects/{id}` | Профиль проекта (read-only): instructions, topics, tone |
| `/admin/review-queue` | Очередь review: take/reject, score, risks |
| `/admin/editorial-queue` | Группы: Needs review / Needs revision / Ready / Rejected |
| `/admin/documents/{id}/revisions` | Read-only история revision snapshots |
| `/admin/hermes` | Hermes status, recent hermes_runs, aliases |
| `/admin/prompts` | Prompt templates (read + activate version) |
| `/admin/prompts/{key}` | История версий, preview, create version |
| `/admin/quality-scores` | Последние content quality scores |
| `/admin/publish-targets` | Publish targets (read-only) |
| `/admin/publish-runs` | Аудит попыток публикации |
| `/admin/source-directories` | Список discovery sources |
| `/admin/source-directories/{id}` | Детали + Run discovery |
| `/admin/discovered-urls` | Очередь URL: Enqueue / Ignore (по одному) |
| `/admin/failed-items` | Failed tasks, LLM, publish + stale running |
| Dashboard | Operational metrics, recent failures, pipeline events |
| Task/Document detail | Pipeline Summary, entity links, publish readiness |

На странице **задачи** и **документа**: блок Rewrite metadata — provider, model_alias, upstream_model, fallback_used, ссылка на llm_run; кнопка **Rerun rewrite**.

На странице документа: parser_name, word_count, extraction_warnings, ссылки JSON/Markdown export.

**Quality Review** на document detail: scores, verdict, risks, recommendations, кнопка **Run quality**.

**Publish safety** показывает QC verdict/score; force republish обходит review, quality и editorial.

**Editorial** блок: status, approve/reject/needs revision/ready; **Timeline** из pipeline + revisions + publish.

Стили: `/static/admin.css`


## Media

- `/admin/media` — assets (status, type, path)
- `/admin/media-jobs` — jobs audit
- Document detail — блок Media: preview, approve/reject, generate placeholder


## Publications & Analytics

- `/admin/publications` — external URLs, status, latest metrics
- `/admin/analytics` — top/low content, snapshots, project summary, aging
- Document detail — блок Publication & performance

## Automation admin

- `/admin/automation` — rules, enable/disable, manual run, heartbeat
- `/admin/automation-runs` — audit log

## Async automation lifecycle (Stage 4B)

- `POST /api/automation/rules/{id}/run` creates `automation_run` with `status=queued` and returns immediately.
- `scrap-scheduler` picks queued runs first, then enqueues due scheduled rules.
- Run statuses: `queued`, `running`, `cancel_requested`, `cancelled`, `completed`, `failed`, `skipped`.
- `progress_json` and structured `logs_json` events for operator visibility.
- `POST /api/automation/runs/{id}/cancel` — queued→cancelled, running→cancel_requested.
- Stale `running` (heartbeat timeout) → `failed` via scheduler recovery or `POST .../mark-failed`.
- **Production default:** `ENABLE_SCHEDULER=false`, `ENABLE_AUTOMATION=false` (rules remain disabled in DB).

### Publish admin (4D)

- `/admin/publish-targets` ? health block per target
- `/admin/publish-runs` ? payload version, retry chain, remote status
- Document detail publish history ? payload version, retry parent, remote status

### Campaign admin (4E)

- `/admin/campaigns`, `/admin/campaigns/{id}` ? coverage, suggestions, duplicates
- `/admin/clusters`, `/admin/clusters/{id}` ? linked docs, performance
- Document detail ? strategy block (cluster, campaign, warnings)


### Content strategy block (4G)

Document detail shows: strategy_allowed, block reason, LLM cleanup status/model/llm_run, test document flag, strategy readiness. Campaign/cluster detail shows excluded_strategy_count.

### Enrichment jobs (4H)

`/admin/enrichment-jobs` — queue, status, retries, latency. Document detail shows latest job and history.


## Deterministic-first orchestration (4I — see ADMIN_UI.md)

```text
Core pipeline (scrape → rewrite → publish)
        ↓
Deterministic extraction (sync, <3s) → strategy gate → topics in metadata
        ↓
Optional async enrichment (llm_enrichment_jobs) → conservative merge → topics enriched
        ↓
Editorial intelligence (review, quality)
        ↓
Campaign intelligence (coverage, clusters) — uses deterministic-first topics
```

### Boundaries

- Enrichment is **optional**; failures do not block publish/rewrite/scraping.
- Worker processes **scraping batch first**, then max 1 enrichment job per poll.
- Scheduler runs enrichment tick **before** automation tick (isolated limits).
- Campaign intelligence ignores failed/stale enrichment; uses `deterministic_result` until merge completes.

### Enrichment job states

`queued` → `running` → `completed` | `failed_retryable` | `failed_terminal` | `cancelled` | `skipped`

Stale `running` jobs (heartbeat timeout) → `failed_retryable` with `[stale recovery]`.

### Merge policy

See `app/services/enrichment_merge_policy.py` — deterministic source-of-truth.

### Enrichment dashboard (4I)

- `/admin/enrichment-dashboard` — queue depth, latency, failures, health
- `/admin/enrichment-jobs` — list with parent lineage column

## Source quality intelligence (4J)

```text
discovery → deterministic quality scoring → quality_scored | quality_blocked
         → manual approve OR enqueue (never auto-enqueue blocked)
```

Deterministic-first; no embeddings. Optional LLM review via `ENABLE_SOURCE_QUALITY_LLM_REVIEW` (off by default).

Guarantees: core pipeline never waits on quality scoring; URLs never deleted.

### Canonical groups (4K)

- `/admin/canonical-groups` — список групп, риск, число документов.
- `/admin/canonical-groups/{id}` — linked docs, similarity links, lineage, strategy warnings.
- Document detail: блок **Canonical / similarity** (group, near duplicates, cannibalization, lineage).
