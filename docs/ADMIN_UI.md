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

