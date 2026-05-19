# Scrap Admin — high-risk templates audit

## Контекст

- **Этап:** Stage 4 **Batch 4** — **audit-only** (без правок templates, CSS, backend).
- **Ветка:** `admin-ui-high-risk-audit-stage-4-batch-4`
- **Base commit:** `8f85c42` (merge Batch 3 route titles)
- **Шаблоны:**
  - `app/admin/templates/document_detail.html` (618 строк)
  - `app/admin/templates/release_candidate_detail.html` (114 строк)
- **Цель:** зафиксировать риски POST/forms/Jinja и подготовить безопасный план **Batch 5** (display-only русификация + smoke).
- **Порт Scrap:** `8800` (не 8000).

### Команды аудита

```bash
cd /opt/scrap
wc -l app/admin/templates/document_detail.html app/admin/templates/release_candidate_detail.html
grep -nE '<form|action=|method=|name=|value=|button|submit|href=' app/admin/templates/document_detail.html
grep -nE '<form|action=|method=|name=|value=|button|submit|href=' app/admin/templates/release_candidate_detail.html
```

---

## Общие ограничения для Batch 5

- **Не менять** routes и URL paths в `action` / `href` для POST-handlers.
- **Не менять** `method` форм (`post` остаётся `post`).
- **Не менять** `name` у `input` / `select` / `textarea` / `checkbox`.
- **Не менять** `value` у `option`, hidden fields, submit semantics.
- **Не менять** enum/status **values** в backend и в `value="{{ ... }}"` — только display-обёртки.
- **Не менять** имена Jinja-переменных (`document`, `publish_readiness`, `detail`, …).
- **Не менять** бизнес-логику, условия feature flags, вложенность `{% if %}` без крайней необходимости.
- **Разрешено:** visible labels (текст кнопок, `<h2>`, `<th>`, `<label>` текст, `title` атрибуты), CSS-классы-обёртки (`.table-scroll`, `.panel`), help-текст рядом с формой — **если** `action` / `method` / `name` / `value` побайтно те же.

---

## document_detail.html

**Размер:** 618 строк · **`<form>` тегов:** 25 (с дубликатами в повторяющихся блоках) · **Уникальных POST action paths:** ~18.

### Pre-existing проблемы (не чинить в Batch 4; учесть в Batch 5)

| # | Строки | Проблема | Риск |
|---|--------|----------|------|
| 1 | 534 | `{% endblock %}` **до** секций Release candidates (537+) и Canonical/similarity (571+) — контент после endblock **не входит** в `{% block content %}` | **high** — секции могут не рендериться или ломать layout |
| 2 | 261–290 / 370–402 | Дублированный блок **Media** (те же POST approve/reject/generate-preview) | **high** — двойные формы на странице |
| 3 | 294–300 / 404–427 | Hermes POST внутри `grid-meta` **и** отдельная панель `#hermes` | **medium** — дубли кнопок |
| 4 | 346–368 | Обрывок analytics: лишний `</p>`, фрагмент Performance/snapshots вне панели `#analytics` | **high** — битая вёрстка |
| 5 | 469–480 | Таблица Publish history: **11 `<th>`**, в `<tr>` меньше `<td>` (смещение колонок) | **medium** — display-only правка `<th>` осторожно |
| 6 | 213 | Mojibake `вЂ"` в pilot-membership (должен быть разделитель) | **low** — только текст |
| 7 | Backend | GET `/admin/documents/{id}` → **500** для id 1,4,5,13: `AttributeError` в `enrichment_service.job_to_dict` при `job is None` | **high** — smoke document detail **невозможен** до bugfix (отдельный Stage 4C, не Batch 5 i18n) |

### Сводка уникальных POST actions

| Action path | method | name / body | Кнопка (EN) |
|-------------|--------|-------------|-------------|
| `/admin/documents/{id}/editorial/operator-review` | post | — | Move to review |
| `/admin/documents/{id}/editorial/needs-revision` | post | — | Needs revision |
| `/admin/documents/{id}/editorial/approve` | post | — | Approve |
| `/admin/documents/{id}/editorial/reject` | post | — | Reject |
| `/admin/documents/{id}/editorial/ready-to-publish` | post | — | Ready to publish |
| `/admin/documents/{id}/rerun-rewrite` | post | — | Rerun rewrite |
| `/admin/documents/{id}/run-review` | post | — | Run review |
| `/admin/documents/{id}/run-seo` | post | — | Run SEO |
| `/admin/documents/{id}/run-quality` | post | — | Run quality |
| `/admin/documents/{id}/media/{media_id}/approve` | post | — | Approve preview |
| `/admin/documents/{id}/media/{media_id}/reject` | post | — | Reject preview |
| `/admin/documents/{id}/media/generate-preview` | post | — | Generate placeholder preview |
| `/admin/documents/{id}/hermes/research` | post | — | Hermes research / Run Hermes research |
| `/admin/documents/{id}/hermes/critique` | post | — | Hermes critique / Run Hermes critique |
| `/admin/documents/{id}/publish-draft` | post | `publish_target_id`, `dry_run`, `force` | Publish draft |
| `/admin/documents/{id}/release-candidates/create` | post | — | Create release candidate |
| `/admin/release-candidates/{rc_id}/run-qa` | post | — | Run QA |
| `/admin/release-candidates/{rc_id}/approve` | post | — | Approve |
| `/admin/release-candidates/{rc_id}/publish-draft` | post | — | Publish draft |
| `/api/documents/{id}/analyze-similarity?deep=false` | post | — | Analyze similarity (API) |

### Таблица блоков

| Блок / секция | EN labels (основные) | Forms POST | action URL | method | name / value | Риск | Batch 5 | Комментарий |
|---------------|----------------------|------------|------------|--------|--------------|------|---------|-------------|
| `_pipeline_summary.html` (include) | из partial | нет | — | — | — | low | да (partial отдельно) | Уже русифицирован в Batch 2 |
| Links (`#` entity-links) | Links, Task, Project, Discovered URL, Review, Pipeline, LLM runs, Publish runs | нет | href only | — | — | low | да | Только ссылки |
| Content strategy (`#strategy`) | Clusters, Campaigns, Enrichment job/history, Strategy gate, Strategy allowed, LLM cleanup, Strategy readiness, Duplicate warnings, Primary topic, Intent, Relevance, Fit, Secondary, Keywords, Entities, Rejected terms, Topic warnings, Cluster coverage, API: extract topics | нет | `/api/documents/{id}/extract-topics` GET link | — | — | medium | да (статика) | Много `{% if strategy_context.* %}`; enum в тексте не переводить как value |
| Publish safety (`#publish-readiness`) | Publish safety, Ready/Not ready, take/reject/review?, score, duplicate, QC, op OK, rev, Ready to publish, Blocked, Missing, Warnings, Publish again (force) | нет | — | — | — | medium | да | Badge-тексты — display; `chk.*` values в badge осторожно |
| Editorial (`#editorial`) | Editorial, Status, Approved for publish, Revision, History, Notes | **5 forms** | `/admin/documents/{id}/editorial/*` | post | — | **high** | только текст кнопок | `ENABLE_EDITORIAL_WORKFLOW` |
| Timeline (`#timeline`) | Timeline, rev | нет | — | — | — | low | да | `ev.label` — данные, не трогать |
| Meta grid (`grid-meta`) | URL, Rewriter (env), Hash, Version, JSON/Markdown export, Задача | **4 forms** (+ Hermes dup) | rerun-rewrite, run-review, run-seo, run-quality, hermes/* | post | — | **high** | только кнопки | Часть полей уже RU (Парсер, Заголовок) |
| Production pilot | Production pilot, priority, next, blockers | нет | — | — | — | low | да | Mojibake на строке 213 |
| Publication & performance (`#analytics`) | Publication, rev, Draft URL, Public URL, Performance, Score, Views, CTR, Trend, Status, Insights, Recent snapshots, Date/Views/CTR/Source, Import metrics, Publication history, No publication record | нет | publications links | — | — | medium | да | `ENABLE_ANALYTICS` |
| Media (`#media`) ×2 | Media, Preview, Alt, Caption, Prompt, Approve/Reject preview, Generate placeholder, Media warnings | **3 forms ×2** | media/approve, reject, generate-preview | post | — | **high** | только кнопки | Дубликат блока |
| Review | Review, Take, Score, Reason | нет | — | — | — | low | да | `review_meta` display |
| Quality Review (`#quality`) | Quality Review, Overall, Readability, SEO, Factual, Structure, Usefulness, Spamminess, Verdict, Risks, Recommendations | нет | — | — | — | medium | да | |
| Hermes (`#hermes`) | Hermes (optional), Run Hermes research/critique, All runs, Latest research/critique, agent, model, fallback, No Hermes runs | **2 forms** | hermes/research, critique | post | — | **high** | только кнопки | `ENABLE_HERMES` |
| SEO metadata | SEO metadata, Title, Description, H1, Slug, Category, Tags, FAQ | нет | — | — | — | low | да | |
| Publish draft (`#publish`) | Publish draft, Target, Force dry-run, Force republish, Publish history table headers | **1 form** | publish-draft | post | `publish_target_id`, `dry_run`, `force` | **high** | label/checkbox text only | `ENABLE_PUBLISHING` |
| Rewrite | Rewrite, Provider, Model alias, Upstream model, Fallback, LLM run, Rewrite error | нет | — | — | — | low | да | |
| Clean / Rewritten / Raw text | Clean text, Rewritten text, Raw text | нет | — | — | — | low | да | |
| Metadata / Raw HTML details | Metadata JSON, Raw HTML (сокращённо) | нет | — | — | — | low | да | summary уже частично RU |
| Release candidates (`#release-candidates`) | Release candidates, ID/Status/QA/Blockers, open, No release candidates, Create release candidate, Run QA, Approve, Publish draft, Payload preview | **4 forms** | create + RC actions | post | — | **high** | только кнопки/заголовки | **После `{% endblock %}`** — риск невидимости |
| Canonical / similarity | Canonical / similarity, Near duplicates, Cannibalization, Strategy, Lineage, Analyze similarity, Группа (RU) | **1 form** | `/api/.../analyze-similarity?deep=false` | post | — | **high** | только кнопка | **После `{% endblock %}`** |

---

## release_candidate_detail.html

**Размер:** 114 строк · **`<form>` тегов:** 12.

### Сводка POST actions

| Action | method | name / fields | Кнопка (EN) |
|--------|--------|---------------|-------------|
| `/admin/release-candidates/{id}/run-qa` | post | — | Run QA |
| `/admin/release-candidates/{id}/approve` | post | — | Approve |
| `/admin/release-candidates/{id}/reject` | post | — | Reject |
| `/admin/release-candidates/{id}/publish-draft` | post | — | Publish draft |
| `/admin/release-candidates/{id}/draft-feedback/notes` | post | `reviewer_name`, `notes`, `required_changes`, `checked_public_visibility`, `checked_seo`, `checked_content`, `checked_media` | Save notes |
| `/admin/release-candidates/{id}/draft-feedback/accepted` | post | — | Mark accepted |
| `/admin/release-candidates/{id}/draft-feedback/needs-edits` | post | — | Mark needs edits |
| `/admin/release-candidates/{id}/draft-feedback/rejected` | post | — | Mark rejected |
| `/admin/publications/{pub_id}/check-visibility` | post | — | Check public visibility (legacy) |
| `/admin/publications/{pub_id}/check-public-status` | post | — | Check public status |
| `/admin/publications/{pub_id}/confirm-public` | post | — | Confirm public |
| `/admin/publications/{pub_id}/mark-not-public` | post | — | Mark not public |

### Таблица блоков

| Блок / секция | EN labels | Forms | action | method | name / value | Риск | Batch 5 | Комментарий |
|---------------|-----------|-------|--------|--------|--------------|------|---------|-------------|
| Page header | Release candidate #, Document, Revision, stale, Status, QA score, analytics ready | нет | links | — | — | low | да | `detail.status` — не менять |
| Blocking issues | Blocking issues, None | нет | — | — | — | low | да | |
| Warnings | Warnings, None | нет | — | — | — | low | да | |
| Checklist | Checklist, Show checklist | нет | — | — | — | low | да | JSON в `<pre>` |
| Actions | Actions, Run QA, Approve, Reject, Publish draft, View payload preview, Publish targets health | **4 forms** | RC + API links | post / GET | — | **high** | только кнопки | API links — href не менять |
| Publish runs | Publish runs, dry_run | нет | — | — | — | low | да | |
| CRMFlow24 Draft Review | Draft URL, No draft URL…, Review status, reviewed, Latest feedback, Reviewer, Notes, Required changes, Checklist legend, Public/SEO/Content/Media checked, Save notes, Mark accepted/needs edits/rejected, Check public visibility (legacy) | **4+1 forms** | draft-feedback/*, check-visibility | post | см. таблицу выше | **high** | label/legend/button text | `reviewer_name` default `operator` — **value не менять** |
| Public visibility (legacy) | Public visibility, Checked at, Blog/Sitemap/RSS, VISIBLE / not visible | нет | — | — | — | medium | да | |
| Feedback history | Feedback history | нет | — | — | — | low | да | |
| Public publication (4Q) | Visibility, Candidate, analytics ready, Public URL, Check public status, Confirm public, Mark not public, Publication detail | **3 forms** | publications/* | post | — | **high** | только кнопки | |

---

## Batch 5 recommended plan

### A. `document_detail.html` — low-risk display only

1. Page-level: нет `<h1>` в шаблоне (title из route) — проверить `title` в routes **отдельным mini-batch** или оставить EN в `<title>` до согласования.
2. Links, Timeline, Review, Rewrite, SEO, Clean/Rewritten/Raw text, details summaries.
3. Content strategy / Publish safety — статичные `<strong>`, `<h2>`, help-абзацы; **не** трогать `strategy_context` field values.
4. Table headers (snapshots, publish history) — только `<th>` текст; **не** менять порядок колонок до fix #5.
5. `.table-scroll` обёртки для wide tables — если не сдвигают DOM внутри форм.

### B. `document_detail.html` — medium-risk

1. Editorial block — 5 POST forms: только visible `button` text + `<h2>`.
2. Meta grid pipeline buttons — rerun/review/seo/quality.
3. Publish draft — `<label>` текст, checkbox labels; **не** `name`/`value`/`option value`.
4. Media / Hermes / RC inline forms — button labels only; **удаление дубликатов** — отдельный **Stage 4C structural fix**, не смешивать с i18n.
5. После каждого подшага: `grep` diff по `action=`, `method=`, `name=`, `value=`.

### C. `release_candidate_detail.html` — low → medium

1. Сначала: h1, h2, None, Show checklist, blocking/warnings labels.
2. Затем: кнопки Actions и draft-feedback (только текст).
3. Publication 4Q кнопки — display only.
4. **Не** менять `placeholder="comma-separated"`, `name="reviewer_name"`, checkbox `name`.

### D. Финальная проверка Batch 5

1. **Предусловие:** fix GET `/admin/documents/{id}` 500 (`job_to_dict` None) — иначе smoke document detail невозможен.
2. **Предусловие (желательно):** перенести RC/Canonical секции **выше** `{% endblock %}` — structural, отдельный commit.
3. `scripts/smoke/run_all.py` + новый `check_admin_document_detail.py` (опционально).
4. curl: URLs из раздела Smoke checklist ниже.
5. `grep -E 'action=|method=|name=|value='` diff vs audit baseline.
6. Manual browser: один POST dry-run (run-quality) на тестовом document.

---

## Explicit no-touch list

- Все POST `action` URL из таблиц выше.
- `method="post"` на всех admin forms.
- `name`: `publish_target_id`, `dry_run`, `force`, `reviewer_name`, `notes`, `required_changes`, `checked_*`.
- `value` у `<option value="{{ t.id }}">` и checkbox states.
- Route decorators и handlers в `app/admin/routes.py`, `analytics_workflow_routes.py`, …
- `app/services/*` (publish, editorial, enrichment, release candidate, draft feedback).
- Publish / approve / reject / QA / Hermes / quality / SEO **логика**.
- Document / release candidate / publication **IDs** в URL patterns.
- Jinja variable names: `document`, `detail`, `publish_readiness`, `strategy_context`, `draft_review`, `public_info`, …
- Feature flag keys: `ENABLE_EDITORIAL_WORKFLOW`, `ENABLE_ANALYTICS`, `ENABLE_MEDIA_PIPELINE`, `ENABLE_HERMES`, `ENABLE_PUBLISHING`.

---

## Smoke checklist for Batch 5

### Примеры ID (read-only, 2026-05-19)

| Сущность | Пример ID | URL | HTTP (audit) |
|----------|-----------|-----|--------------|
| Document | **13** (editorial-queue), также 1, 4, 5 | `http://127.0.0.1:8800/admin/documents/13` | **500** (pre-existing backend) |
| Release candidate | **9** | `http://127.0.0.1:8800/admin/release-candidates/9` | **200** |
| Task | **17** | `http://127.0.0.1:8800/admin/tasks/17` | **200** |

### GET smoke (минимум)

- [ ] `/admin` → 200
- [ ] `/admin/documents/{id}` → 200 (**после fix enrichment None**)
- [ ] `/admin/release-candidates/{id}` → 200 (example: **9**)
- [ ] `/admin/tasks/17` → 200
- [ ] `/admin/editorial-queue` → 200
- [ ] `/admin/release-candidates` → 200
- [ ] `.venv/bin/python scripts/smoke/run_all.py` → PASS
- [ ] `grep` form attributes: нет diff по `action`/`method`/`name`/`value`
- [ ] `storage/logs/app.log` — нет новых traceback после smoke

---

## Audit metadata

- **Дата аудита (UTC):** 2026-05-19
- **Аудитор:** Cursor agent (Batch 4 audit-only)
- **Изменения кода в Batch 4:** нет (только этот документ + PROJECT_LOG + redesign-plan)
