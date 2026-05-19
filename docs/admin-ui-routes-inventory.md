# Scrap Admin — инвентаризация маршрутов

> Аудит от **2026-05-19**. Источник правды: `/opt/scrap/app/admin/*.py` на сервере `hermes`.  
> Маршрут `/admin/editorial` **не существует** — editorial UI: `/admin/editorial-queue`.

## Стек (кратко)

| Компонент | Путь |
|-----------|------|
| Основные routes | `app/admin/routes.py` |
| Доп. routes | `app/admin/manual_url_routes.py`, `pilot_routes.py`, `analytics_workflow_routes.py` |
| Подключение | `app/main.py` → `include_router(admin_router)` + sub-routers в конце `routes.py` |
| Templates | `app/admin/templates/` (Jinja2, `base.html` + 52 страницы/partials) |
| CSS | `app/admin/static/admin.css` → mount `/static` |
| Layout / меню | `app/admin/templates/base.html` (горизонтальный `<nav>` в `.topbar`) |

---

## GET-страницы (HTML)

| URL | Название (title) | Template | Основные действия | Формы/POST | Риск | Приоритет | Комментарий |
|-----|------------------|----------|-------------------|------------|------|-----------|-------------|
| `/admin` | Dashboard | `dashboard.html` | Ссылки на tasks/documents, метрики | Нет | low | P0 | Точка входа; sidebar anchor |
| `/admin/failed-items` | Failed Items | `failed_items.html` | Mark skipped, reset stale | Да (inline POST) | medium | P1 | Операционная страница ошибок |
| `/admin/tasks/new` | Добавить URL | `task_new.html` | POST: создать task (`source_url`, `parser_type`) | Да | medium | P0 | **Проблемная страница** — нет help-блока |
| `/admin/tasks/{task_id}` | Задача #{id} | `task_detail.html` | Mark skipped; ссылки на document, logs | Да (1 POST) | medium | P0 | Pipeline summary, entity links |
| `/admin/documents/{document_id}` | Документ #{id} | `document_detail.html` | Rewrite, review, SEO, quality, Hermes, editorial, publish, media, RC | Да (много POST) | **high** | P1 | 618 строк; **не трогать action URLs** |
| `/admin/documents/{document_id}/revisions` | Revisions — doc #{id} | `document_revisions.html` | Read-only история | Нет | low | P2 | |
| `/admin/publish-targets` | Publish Targets | `publish_targets.html` | Read-only список targets | Нет | low | P2 | |
| `/admin/publish-runs` | Publish Runs | `publish_runs.html` | Read-only аудит | Нет | low | P2 | |
| `/admin/settings` | Настройки | `settings.html` | Read-only env flags | Нет | low | P2 | Уже частично на русском |
| `/admin/projects` | Projects | `projects.html` | Ссылки на project detail | Нет | low | P2 | |
| `/admin/projects/{project_id}` | Project {slug} | `project_detail.html` | Read-only профиль | Нет | low | P2 | |
| `/admin/review-queue` | Review Queue | `review_queue.html` | Ссылки на documents | Нет | low | P1 | Ранний этап pipeline |
| `/admin/llm-runs` | LLM Runs | `llm_runs.html` | Read-only аудит LLM | Нет | low | P2 | |
| `/admin/pipeline-events` | Pipeline Events | `pipeline_events.html` | Read-only события | Нет | low | P2 | В меню как «Pipeline» |
| `/admin/source-directories` | Source Directories | `source_directories.html` | Ссылки на detail | Нет | low | P1 | Discovery |
| `/admin/source-directories/{directory_id}` | Source: {name} | `source_directory_detail.html` | POST: Run discovery | Да | medium | P1 | |
| `/admin/discovered-urls` | Discovered URLs | `discovered_urls.html` | Фильтры (?status=); Enqueue / Approve quality / Ignore | Да (inline) | medium | P0 | **Проблемная страница** — табы EN, широкая таблица |
| `/admin/prompts` | Prompts | `prompts.html` | Ссылки на prompt detail | Нет | low | P2 | |
| `/admin/prompts/{key}` | Prompt {key} | `prompt_detail.html` | POST: create version, activate | Да | medium | P2 | |
| `/admin/quality-scores` | Quality Scores | `quality_scores.html` | Read-only scores | Нет | low | P2 | Дублирует label «Quality» в меню |
| `/admin/publications` | Publications | `publications.html` | Ссылки на publication detail | Нет | low | P1 | |
| `/admin/publications/{publication_id}` | Publication #{id} | `publication_detail.html` | Check visibility/status, confirm public, mark not public | Да | medium | P1 | |
| `/admin/analytics` | Analytics | `analytics.html` | Read-only аналитика | Нет | low | P2 | |
| `/admin/analytics-ready` | Analytics ready | `analytics_ready.html` | Ссылки на import | Нет | low | P2 | |
| `/admin/publications/{publication_id}/analytics/import` | Import metrics — publication #{id} | `analytics_import.html` | POST: import snapshot | Да | medium | P2 | |
| `/admin/operations` | Operations | `operations.html` | Операционные блоки, ссылки | Возможны POST-ссылки | low | P2 | |
| `/admin/hermes` | Hermes | `hermes.html` | Read-only status | Нет | low | P2 | |
| `/admin/editorial-queue` | Editorial Queue | `editorial_queue.html` + `_editorial_queue_table.html` | Open doc, Create RC, Run QC | Да (inline в partial) | medium | P0 | **Проблемная страница**; alias «Editorial» в меню |
| `/admin/media` | Media Assets | `media.html` | Ссылки на documents | Нет | low | P2 | |
| `/admin/source-quality` | Source Quality | `source_quality_dashboard.html` | Read-only метрики | Нет | low | P1 | |
| `/admin/enrichment-dashboard` | Enrichment Dashboard | `enrichment_dashboard.html` | Ссылки | Нет | low | P2 | |
| `/admin/enrichment-jobs` | LLM Enrichment Jobs | `enrichment_jobs.html` | Read-only jobs | Нет | low | P2 | |
| `/admin/media-jobs` | Media Jobs | `media_jobs.html` | Read-only jobs | Нет | low | P2 | |
| `/admin/llm/smoke` | LLM Smoke Test | `llm_smoke.html` | POST: run smoke | Да | medium | P2 | |
| `/admin/automation` | Automation | `automation.html` | Run / enable / disable rules | Да | medium | P2 | |
| `/admin/automation-runs` | Automation Runs | `automation_runs.html` | Ссылки на run detail | Нет | low | P2 | |
| `/admin/automation-runs/{run_id}` | Run #{id} | `automation_run_detail.html` | Cancel, mark failed | Да | medium | P2 | |
| `/admin/system` | System | `system.html` | Read-only system info | Нет | low | P2 | |
| `/admin/campaigns` | Campaigns | `campaigns.html` | Ссылки на campaign | Нет | low | P2 | |
| `/admin/campaigns/{campaign_id}` | Campaign {name} | `campaign_detail.html` | Read-only | Нет | low | P2 | |
| `/admin/clusters` | Topic Clusters | `clusters.html` | Ссылки на cluster | Нет | low | P2 | |
| `/admin/clusters/{cluster_id}` | Cluster {name} | `cluster_detail.html` | Read-only | Нет | low | P2 | |
| `/admin/canonical-groups` | Canonical groups | `canonical_groups_list.html` | Ссылки на group | Нет | low | P2 | **Нет в текущем меню** — добавить в sidebar |
| `/admin/canonical-groups/{group_id}` | Canonical #{id} | `canonical_group_detail.html` | Read-only | Нет | low | P2 | Нет в меню |
| `/admin/release-candidates` | Release candidates | `release_candidates_list.html` | Ссылки на RC detail | Нет | low | P1 | **Нет в текущем меню** |
| `/admin/release-candidates/{candidate_id}` | Release candidate #{id} | `release_candidate_detail.html` | Run QA, approve, reject, publish-draft, draft feedback | Да (много) | **high** | P1 | Нет в меню; много POST |
| `/admin/draft-reviews` | Draft reviews | `draft_reviews_list.html` | Ссылки на RC | Нет | low | P1 | |
| `/admin/pilots` | Production pilots | `pilots.html` | Ссылки на pilot detail | Нет | low | P2 | |
| `/admin/pilots/{pilot_id}` | {pilot name} | `pilot_detail.html` | Add/remove document, refresh | Да | medium | P2 | |
| `/admin/manual-urls` | *(title не передаётся)* | `manual_urls.html` | POST: bulk/single URL intake | Да | medium | P1 | **Нет в меню**; баг: пустой `<h1>` |

---

## POST-only actions (без отдельной HTML-страницы)

| URL | Redirect / ответ | Вызывается из | Риск |
|-----|------------------|---------------|------|
| `POST /admin/tasks/new` | → `/admin/tasks/{id}` | `task_new.html` | medium |
| `POST /admin/tasks/{id}/mark-skipped` | → task detail | `failed_items`, `task_detail` | medium |
| `POST /admin/tasks/{id}/reset-stale` | → `/admin/failed-items` | `failed_items` | medium |
| `POST /admin/discovered-urls/{id}/enqueue` | → task или discovered-urls | `discovered_urls.html` | medium |
| `POST /admin/discovered-urls/{id}/approve-quality` | → discovered-urls | `discovered_urls.html` | medium |
| `POST /admin/discovered-urls/{id}/ignore` | → discovered-urls | `discovered_urls.html` | medium |
| `POST /admin/source-directories/{id}/discover` | → directory detail | `source_directory_detail.html` | medium |
| `POST /admin/documents/{id}/rerun-rewrite` | → document | `document_detail.html` | **high** |
| `POST /admin/documents/{id}/run-review` | → document | document, editorial partial | **high** |
| `POST /admin/documents/{id}/run-seo` | → document | document | **high** |
| `POST /admin/documents/{id}/run-quality` | → document | document, editorial partial | **high** |
| `POST /admin/documents/{id}/hermes/research` | → document | document | **high** |
| `POST /admin/documents/{id}/hermes/critique` | → document | document | **high** |
| `POST /admin/documents/{id}/editorial/*` (5 actions) | → document | document | **high** |
| `POST /admin/documents/{id}/publish-draft` | → document | document | **high** |
| `POST /admin/documents/{id}/media/*` (3 actions) | → document | document | **high** |
| `POST /admin/documents/{id}/release-candidates/create` | → RC detail | document, editorial partial | **high** |
| `POST /admin/prompts/{key}/versions` | → prompt detail | `prompt_detail.html` | medium |
| `POST /admin/prompts/{key}/versions/{vid}/activate` | → prompt detail | `prompt_detail.html` | medium |
| `POST /admin/release-candidates/{id}/run-qa` | → RC detail | `release_candidate_detail.html` | **high** |
| `POST /admin/release-candidates/{id}/approve` | → RC detail | RC detail | **high** |
| `POST /admin/release-candidates/{id}/reject` | → RC detail | RC detail | **high** |
| `POST /admin/release-candidates/{id}/publish-draft` | → RC detail | RC detail | **high** |
| `POST /admin/release-candidates/{id}/draft-feedback/*` (3) | → RC detail | RC detail | **high** |
| `POST /admin/publications/{id}/check-visibility` | → publication | publication detail | medium |
| `POST /admin/publications/{id}/check-public-status` | → publication | publication detail | medium |
| `POST /admin/publications/{id}/confirm-public` | → publication | publication detail | medium |
| `POST /admin/publications/{id}/mark-not-public` | → publication | publication detail | medium |
| `POST /admin/automation/rules/{id}/run\|enable\|disable` | → automation | `automation.html` | medium |
| `POST /admin/automation-runs/{id}/cancel\|mark-failed` | → run detail | automation run detail | medium |
| `POST /admin/pilots/{id}/add-document\|remove-document\|refresh` | → pilot detail | `pilot_detail.html` | medium |
| `POST /admin/manual-urls` | re-render manual_urls | `manual_urls.html` | medium |
| `POST /admin/publications/{id}/analytics/import` | → import form / publication | `analytics_import.html` | medium |
| `POST /admin/llm/smoke` | re-render llm_smoke | `llm_smoke.html` | medium |

**Итого:** 49 GET HTML + 44 POST action (по `rg '@router.(get|post)' app/admin`).

---

## Маршруты в меню vs реальность

| Ссылка в `base.html` | Route найден | Примечание |
|----------------------|--------------|------------|
| Все 32 пункта `<nav>` | ✅ | URL совпадают с `@router.get` |
| `/admin/editorial` | ❌ | **Требует проверки** — пользователи могут ожидать alias; реальный URL: `/admin/editorial-queue` |
| `/admin/manual-urls` | ✅ route, ❌ меню | Route есть, в nav отсутствует |
| `/admin/release-candidates` | ✅ route, ❌ меню | Route есть, в nav отсутствует |
| `/admin/canonical-groups` | ✅ route, ❌ меню | Route есть, в nav отсутствует |

---

## Partials (не отдельные routes)

| Файл | Используется в |
|------|----------------|
| `_pipeline_summary.html` | `task_detail.html`, `document_detail.html` |
| `_editorial_queue_table.html` | `editorial_queue.html` |

---

## Ключевые templates по сложности

| Template | Строк | POST forms (approx) | Риск визуальной правки |
|----------|-------|---------------------|------------------------|
| `document_detail.html` | 618 | ~15+ | **high** |
| `release_candidate_detail.html` | 114 | ~6 | **high** |
| `discovered_urls.html` | 118 | 3 per row | medium |
| `editorial_queue.html` + partial | 27 + 34 | 2 per row | medium |
| `task_new.html` | 18 | 1 | medium |
| `base.html` | 53 | 0 | medium (layout — затрагивает все страницы) |
