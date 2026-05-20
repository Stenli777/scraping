# Admin UI

Base: **https://scrap.crmflow24.ru/admin**

**План редизайна (2026-05-19):** [admin-ui-redesign-plan.md](./admin-ui-redesign-plan.md) · [admin-ui-routes-inventory.md](./admin-ui-routes-inventory.md)


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

### Release candidates
- `/admin/release-candidates`, detail with approve/reject/publish
- Document detail: Release Candidates block
- Editorial queue: RC status, QA score, blockers

### Draft review (4N)

- **Release candidate detail** — блок «CRMFlow24 Draft Review»: draft URL, checklist, notes, Mark accepted / needs edits / rejected, Check public visibility.
- **`/admin/draft-reviews`** — очередь publications с `draft_review_status` pending / needs_edits.

### Operations — Release Operations block (4O)

Read-only summary: latest `published_draft` candidates, publications missing feedback, needs_edits/rejected counts, smoke/test warnings. Links to draft reviews and release candidates.

### Publish targets safety (4P)

`/admin/publish-targets` — target class (mock/test/production), safety warnings, smoke scope.
`/admin/operations` — publish target safety summary, smoke command hints.

## 2026-05-18 — этап 4Q

- `/admin/publications` — колонки visibility, analytics ready.
- `/admin/publications/{id}` — detail: check / confirm / mark not public.
- Release candidate detail — блок Public publication (4Q).
- `/admin/operations` — Post-publication tracking counters.
- `/admin/analytics-ready`, `/admin/publications/{id}/analytics/import`, performance history on publication detail.
- `/admin/pilots`, `/admin/pilots/{id}` — progress, items, suggested candidates, safe action links.
- `/admin/manual-urls` — paste URLs for intake + optional enqueue.

## 4W — publish failure badges
- `/admin/publish-runs`, `/admin/failed-items`: badges `historical env`, `test target` для старых token/env ошибок.
- `/admin/agents` — агенты (промпты RU); `/admin/projects/new`, `/admin/projects/{id}/agents`

## 2026-05-19 — этап 4Z (agent editor UX)

### UX-правила
1. **Навигация сверху и снизу** — на длинных страницах агентов/проекта дублировать кнопки возврата.
2. **Компактные формы** — связанные поля в одной строке (название, slug, домен, язык; JSON темы).
3. **Понятные кнопки** — «Сохранить новую версию агента», «Сохранить и сделать активной для проекта».
4. **Редактор агента** — textarea для system/user, preview effective prompt.

### Термины
- **System prompt** — роль и правила агента.
- **User prompt** — шаблон задачи с переменными документа.
- **Project override** — проектная версия только для этого проекта.

### Страницы
- Project agent detail — редактор override.
- Project tasks / documents — списки с фильтрами.

### topic_cleanup_v1
- Исправлена UTF-8 в code fallback prompts (раньше были знаки вопроса).
- Явное сообщение при использовании fallback из кода.

## 2026-05-20 — этап 4AA (UX hardening + save-flow)

### Исправлено
- **500 при сохранении агента**: отсутствовал `prompt_templates` для `topic_cleanup_v1` → `ensure_prompt_template()` перед созданием версии; дубликат версии — auto-suffix timestamp; ошибки → redirect `?error=`, не 500.
- Примеры prompt свернуты в `<details>`; форма редактирования наверху.
- Таблицы tasks/documents: `page_size` 10/50/100, `admin-table-viewport`, styled selects.
- `/admin/agents/new` — создание custom-агента (не в pipeline до явного подключения).
- `scripts/test_agent_save_flow.py` — regression save/activate/disable на test project.

### UX-правила
1. Длинные примеры — только в `<details>`.
2. POST submit страниц — regression smoke (`test_agent_save_flow.py`).
3. Таблицы проекта — полная ширина, page size selector, inner scroll.
4. Select — класс `.admin-select`, единый стиль.
