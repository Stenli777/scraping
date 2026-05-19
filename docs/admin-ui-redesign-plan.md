# Scrap Admin — план визуального редизайна

> Документ подготовлен **2026-05-19** (этап: аудит + план).  
> **Этап 1 выполнен** (ветка `admin-ui-sidebar-stage-1`, commit `f69e118`, merge `eebb951`).  
> **Этап 2 выполнен** (ветка `admin-ui-kit-stage-2`, merge `f87e5c9`).  
> **Этап 3 выполнен** (ветка `admin-ui-p0-pages-stage-3`): P0 templates + help-блоки + tabs + table-scroll.  
> **Stage 3B:** fix filter `/admin/discovered-urls?status=...` (query order в routes.py).  
> **Stage 4 Batch 4 (audit-only):** high-risk templates audit — [admin-ui-high-risk-audit.md](./admin-ui-high-risk-audit.md).  
> **Stage 4C (backend fix):** ветка `admin-ui-document-detail-fix-stage-4b` — `/admin/documents/{id}` 500 → `job_to_dict(None)` guard.  
> **Batch 5 выполнен** (ветка `admin-ui-final-high-risk-polish-stage-5`): display-only polish high-risk detail pages.  
> **Visual polish + detail clarity** merged (`ad611b4`).  
> **Hybrid operator workflow** (`admin-ui-sidebar-workflow-hybrid`): pipeline sidebar, dashboard onboarding — [admin-operator-workflow.md](./admin-operator-workflow.md).  
> Not merged as-is: `admin-ui-operator-workflow` (`203248a`).
> Детальная таблица маршрутов: [admin-ui-routes-inventory.md](./admin-ui-routes-inventory.md).  
> Существующий обзор: [ADMIN_UI.md](./ADMIN_UI.md).

---

## Дорожная карта UI/UX (8 этапов)

| Этап | Название | Scope | Статус |
|------|----------|-------|--------|
| 1 | Sidebar + layout | `base.html`, `admin.css` | **Выполнен** (`f69e118`, merge `eebb951`) |
| 2 | UI kit | `admin.css`, labels в `base.html` | **Выполнен** (ветка `admin-ui-kit-stage-2`) |
| 3 | P0 страницы | `task_new`, `discovered_urls`, `editorial_queue`, partial | **Выполнен** (ветка `admin-ui-p0-pages-stage-3`) |
| 4 | Русификация display layer | меню, заголовки, таблицы, статусы, кнопки | **Следующий** |
| 5 | Help-блоки | P1 страницы | Запланирован |
| 6 | P1 страницы | dashboard, task detail, review queue, source dirs, failed items, manual urls, RC list, draft reviews, publications | Запланирован |
| 7 | High-risk точечно | document detail, RC detail, revisions | **Batch 5 выполнен** — polish по [admin-ui-high-risk-audit.md](./admin-ui-high-risk-audit.md) |
| 8 | Финальная полировка | mobile, a11y, active states, legacy CSS cleanup | Запланирован |

**Примечание:** Scrap admin слушает порт **8800** (не 8000 — там Hermes). Editorial route: `/admin/editorial-queue` (не `/admin/editorial`).

## Правило ведения документации

- После каждого UI/UX этапа и bugfix обязательно обновлять `docs/PROJECT_LOG.md`.
- В `PROJECT_LOG.md` писать: ветку, commit, изменённые файлы, команды, smoke/curl, ошибки, restart/deploy, следующий шаг.
- `docs/admin-ui-redesign-plan.md` обновлять при изменении roadmap/status этапов.
- `docs/admin-ui-routes-inventory.md` обновлять только при изменении или уточнении routes/forms/POST.
- Документация должна быть закоммичена вместе с этапом или отдельным docs commit.
- Документация должна быть синхронизирована и на сервере `/opt/scrap`, и в локальной копии через git.
- Если pre-existing bug стал виден после UI-правки — фиксировать отдельным Stage X.B bugfix в `PROJECT_LOG.md`.


1. Перейти от перегруженного **горизонтального** меню к **вертикальному sidebar** с группами и pipeline-first иерархией.
2. Унифицировать кнопки, табы-фильтры, таблицы, бейджи статусов.
3. Русифицировать интерфейс (заголовки, колонки, кнопки, статусы, подсказки).
4. Добавить **help-блоки** на страницах: назначение, действия, значения статусов.
5. Сохранить **100% работоспособность** существующих routes, форм, POST action URLs и backend-логики.

**Не цель этого этапа:** массовая перепись страниц, смена frontend-стека, изменение API/моделей/воркеров.

---

## Что нельзя ломать

| Категория | Ограничение |
|-----------|-------------|
| Routes | Все `@router.get/post` в `app/admin/*.py` — URL и HTTP-методы без изменений |
| Forms | `method`, `action`, `name` полей форм — без переименования |
| POST handlers | Redirect targets (`303` → task/document/discovered-urls и т.д.) |
| Backend | `app/services/*`, models, alembic, workers/jobs |
| Partials | Логика `_pipeline_summary.html`, `_editorial_queue_table.html` — только обёртка/стили |
| Static mount | `/static` → `app/admin/static/` |
| Внешние ссылки | `/health`, `/health/ready`, `/docs` — target="_blank" сохранить |

**Правило diff:** на каждом этапе — маленькие PR/коммиты; один layout или 3–5 страниц за раз, не «всё сразу».

---

## Текущие проблемы UI

### Навигация (`base.html`)

- **32+ ссылки** в одной горизонтальной строке `.topbar nav` — элементы слипаются (`margin-left: 1rem`, нет переноса групп).
- Смешение языков: «Добавить URL», «Настройки» рядом с «Dashboard», «Failed», «Review Queue».
- Дублирование смысла: два пункта «Quality» (`/admin/source-quality` и `/admin/quality-scores`).
- Составные пункты через ` · `: Enrichment/Jobs, Discovery/Discovered URLs.
- **Routes без пункта меню:** `/admin/manual-urls`, `/admin/release-candidates`, `/admin/canonical-groups`.

### Страницы-референсы (скриншоты проблем)

#### `/admin/tasks/new` (`task_new.html`)

- Минимальная форма без контекста: нет help «что произойдёт после submit».
- Title «Добавить URL» — OK; кнопка «Создать задачу» — OK.
- POST на `/admin/tasks/new` с полями `source_url`, `parser_type` — **не трогать**.

#### `/admin/discovered-urls` (`discovered_urls.html`)

- Фильтры оформлены как `.btn` ссылки (All, Discovered, Duplicate…) — нет визуального «активного таба».
- Заголовки колонок на EN (Quality, Rel, Spam, Actions…); статусы — raw enum в `.badge`.
- Широкая таблица (16 колонок) без horizontal scroll wrapper.
- Inline POST: `enqueue`, `approve-quality`, `ignore` — **action URLs фиксированы**.

#### `/admin/editorial-queue` (не `/admin/editorial`)

- Четыре секции (Needs review / Needs revision / Ready / Rejected) — заголовки EN.
- Partial `_editorial_queue_table.html`: колонки EN, кнопки «Open», «RC», «QC»; статусы в `<code>`.
- POST из partial: `/admin/documents/{id}/release-candidates/create`, `/admin/documents/{id}/run-quality`.

### CSS (`admin.css`, 132 строки)

- Есть база: CSS variables, `.table`, `.badge`, `.btn`, `.warn-box`, status-* классы.
- **Нет:** sidebar layout, nav groups, active link, tab component, help-block, table responsive wrapper, единый secondary/danger button variant.

### Сторонние UI-библиотеки

**Рекомендация: не подключать** (Bootstrap, Tabler, AdminLTE и т.п.) на первых этапах.

- Риск конфликта с существующими классами (`.btn`, `.table`, `.badge`).
- Jinja-админка уже самодостаточна; 132 строки CSS легко расширить.
- Тяжёлый переезд не оправдан при рабочем функционале.

---

## Найденный стек админки

```
FastAPI
├── app/main.py
│   ├── include_router(admin_router)
│   └── app.mount("/static", StaticFiles(directory=app/admin/static))
└── app/admin/
    ├── routes.py              # основной router + include sub-routers
    ├── manual_url_routes.py
    ├── pilot_routes.py
    ├── analytics_workflow_routes.py
    ├── static/admin.css
    └── templates/
        ├── base.html          # layout + horizontal nav
        ├── dashboard.html
        ├── task_new.html
        ├── discovered_urls.html
        ├── editorial_queue.html
        ├── _editorial_queue_table.html
        ├── _pipeline_summary.html
        └── … (ещё ~45 templates)
```

**Jinja:** `Jinja2Templates(directory=app/admin/templates)` в `routes.py` (и дублируется в `manual_url_routes.py`).

**JS:** отдельных admin JS-файлов **нет** — только HTML/CSS. Это упрощает редизain (не ломаем bundler).

---

## Инвентаризация ключевых templates / layouts / static

| Приоритет | Файл | Роль |
|-----------|------|------|
| P0 | `base.html` | Единственный layout; меню; CSS link |
| P0 | `admin.css` | Все стили admin |
| P0 | `task_new.html` | Форма добавления URL |
| P0 | `discovered_urls.html` | Очередь discovery |
| P0 | `editorial_queue.html` | Editorial queue |
| P0 | `_editorial_queue_table.html` | Таблица editorial (partial) |
| P1 | `dashboard.html` | Landing после sidebar |
| P1 | `task_detail.html` | Карточка задачи |
| P1 | `document_detail.html` | Самая сложная страница (618 строк) |
| P1 | `_pipeline_summary.html` | Pipeline block (partial) |
| P2 | Остальные 40+ templates | Поэтапно после P0/P1 |

---

## Предлагаемая структура sidebar

Подразделы — **некликабельные** заголовки (`<div class="nav-group-label">`). Ссылки — только из подтверждённых routes (см. inventory).

```
Scrap Admin (brand → /admin)

── Обзор ──
  Dashboard                    /admin
  Сбои и зависшие              /admin/failed-items
  Операции                     /admin/operations
  Система                      /admin/system

── Импорт и discovery ──
  Добавить URL                 /admin/tasks/new
  Ручной импорт URL            /admin/manual-urls          ← route есть, в старом меню не было
  Источники (directories)      /admin/source-directories
  Найденные URL                /admin/discovered-urls
  Качество источников          /admin/source-quality

── Очереди и редактура ──
  Review Queue                 /admin/review-queue
  Editorial Queue              /admin/editorial-queue      ← не /admin/editorial
  Draft reviews                /admin/draft-reviews
  Release candidates           /admin/release-candidates   ← route есть, в старом меню не было

── Качество ──
  Quality scores               /admin/quality-scores
  Canonical groups             /admin/canonical-groups     ← route есть, в старом меню не было

── Медиа и обогащение ──
  Media                        /admin/media
  Media Jobs                   /admin/media-jobs
  Enrichment                   /admin/enrichment-dashboard
  Enrichment Jobs              /admin/enrichment-jobs

── Публикация ──
  Publish Targets              /admin/publish-targets
  Publish Runs                 /admin/publish-runs
  Publications                 /admin/publications
  Analytics ready              /admin/analytics-ready
  Analytics                    /admin/analytics
  Pilots                       /admin/pilots

── LLM и промпты ──
  Prompts                      /admin/prompts
  LLM Runs                     /admin/llm-runs
  LLM Smoke                    /admin/llm/smoke
  Hermes                       /admin/hermes

── Организация контента ──
  Projects                     /admin/projects
  Campaigns                    /admin/campaigns
  Clusters                     /admin/clusters
  Automation                   /admin/automation
  Automation Runs              /admin/automation-runs

── Справка / API ──
  Pipeline Events              /admin/pipeline-events
  Настройки                    /admin/settings
  Health                       /health          (target=_blank)
  Ready                        /health/ready    (target=_blank)
  API Docs                     /docs            (target=_blank)
```

**Миграция меню:** все 32 старые ссылки из `base.html` сохраняются (ни одна не удаляется без redirect/alias). Новые пункты (manual-urls, release-candidates, canonical-groups) — **добавление**, не замена.

**Опционально позже:** redirect GET `/admin/editorial` → `/admin/editorial-queue` (только backend, отдельный mini-PR; не обязателен для UI-этапа).

---

## Список страниц для поэтапной правки

### P0 — первые (после layout)

| # | URL | Template | Задачи UI |
|---|-----|----------|-----------|
| 1 | `/admin` | `dashboard.html` | Help-блок; русские подписи метрик |
| 2 | `/admin/tasks/new` | `task_new.html` | Help; подсказка по parser_type |
| 3 | `/admin/discovered-urls` | `discovered_urls.html` | Табы-фильтры; RU колонки; scroll wrapper |
| 4 | `/admin/editorial-queue` | `editorial_queue.html`, partial | RU секции; унифицировать кнопки |
| 5 | `base.html` + `admin.css` | layout | Sidebar (этап 1) |

### P1 — второй заход

| URL | Template | Примечание |
|-----|----------|------------|
| `/admin/tasks/{id}` | `task_detail.html` | Pipeline summary styling |
| `/admin/review-queue` | `review_queue.html` | Таблица + help |
| `/admin/source-directories` | `source_directories.html` | |
| `/admin/source-directories/{id}` | `source_directory_detail.html` | Кнопка Discover |
| `/admin/failed-items` | `failed_items.html` | POST actions |
| `/admin/manual-urls` | `manual_urls.html` | Добавить title + help |
| `/admin/release-candidates` | `release_candidates_list.html` | Включить в nav |
| `/admin/draft-reviews` | `draft_reviews_list.html` | |
| `/admin/publications` | `publications.html` | |

### P2 — остальное

Все оставшиеся GET-страницы из inventory; `document_detail.html` и `release_candidate_detail.html` — **последними** (high risk, много POST).

---

## Этап 1: общий layout + sidebar

**Scope:** только `base.html`, `admin.css` (+ опционально `admin-nav.html` partial).

**Действия:**

1. Добавить CSS grid/flex: `.layout { display: flex }`, `.sidebar`, `.main-content`.
2. Перенести `<nav>` из `.topbar` в `.sidebar`; сгруппировать по структуре выше.
3. Подразделы: `.nav-group-label` (не `<a>`).
4. Активная ссылка: Jinja `request.url.path` starts with — класс `.nav-active`.
5. Topbar оставить минимальным: brand + optional mobile toggle.
6. **Не менять** `href` значений; **не удалять** старые пункты (можно скрыть в «legacy horizontal» до проверки, но лучше сразу sidebar со всеми пунктами).
7. `.container` → padding под sidebar; проверить max-width на wide tables.

**Не делать на этапе 1:** правки дочерних templates, переименование routes, JS frameworks.

---

## Этап 2: единая система кнопок / табов / таблиц / бейджей

**Scope:** `admin.css` + macro/partial (рекомендуется `templates/_ui_macros.html`).

**Компоненты:**

| Компонент | Классы | Использование |
|-----------|--------|---------------|
| Primary button | `.btn.btn-primary` | Submit главного действия |
| Secondary | `.btn.btn-secondary` | Open, фильтры |
| Danger | `.btn.btn-danger` | Reject, Ignore (осторожно — не менять type=submit) |
| Tab bar | `.tabs`, `.tab`, `.tab.active` | discovered-urls status filters |
| Table | `.table`, `.table-scroll` | wrapper overflow-x |
| Badge | `.badge.status-{enum}` | маппинг RU label через macro |
| Help | `.help-block`, `.help-block-title` | этап 4 или заготовка |

**Порядок внедрения CSS:** сначала добавить новые классы **рядом** со старыми (`.btn.primary` → alias `.btn-primary`); не удалять `.btn.primary` до конца миграции.

**Первые страницы для компонентов:** `discovered_urls.html`, `_editorial_queue_table.html`, `task_new.html`.

---

## Этап 3: русификация

**Scope:** titles в routes (опционально, только display), templates, badges.

**Принцип:** enum values в backend **не менять**; перевод только в display layer (Jinja macro `status_label('discovered')` → «Обнаружен»).

**Приоритет перевода:**

1. Меню sidebar (этап 1 частично)
2. P0 страницы (tasks/new, discovered-urls, editorial-queue)
3. Общие колонки таблиц: ID, URL, Status, Actions, Project
4. Dashboard, failed-items
5. document_detail — по блокам (не одним diff)

**Словарь статусов (черновик):**

| Enum | RU |
|------|-----|
| discovered | Обнаружен |
| enqueued | В очереди |
| ignored | Игнор |
| duplicate | Дубликат |
| quality_blocked | Заблокирован качеством |
| done | Готово |
| error | Ошибка |
| needs_review | Требует проверки |
| ready_to_publish | Готов к публикации |

Полный словарь — отдельный `_status_labels.html` или Python dict в `admin_context_service` (только display, без миграций).

---

## Этап 4: help-блоки на страницах

**Шаблон блока:**

```html
<aside class="help-block">
  <p class="help-block-title">О странице</p>
  <p>…назначение…</p>
  <p class="help-block-title">Действия</p>
  <ul><li>…</li></ul>
  <p class="help-block-title">Статусы</p>
  <ul><li>…</li></ul>
</aside>
```

**Минимальный набор P0:**

| Страница | Содержание help |
|----------|-----------------|
| `/admin/tasks/new` | Создаёт scrape task; после submit — redirect на task; parser_type можно оставить default |
| `/admin/discovered-urls` | Очередь URL из discovery; фильтры по status; Enqueue → task; Ignore → исключение |
| `/admin/editorial-queue` | Группы editorial workflow; Open → document; RC → release candidate; QC → run quality |
| `/admin` | Обзор pipeline; ссылки на последние tasks |

Реализация: inline в template или `{% include "_help/task_new.html" %}` — без логики.

---

## Smoke-test checklist

Запускать **после каждого этапа** (layout, components, i18n, help).

### Базовая навигация (GET, ожидание 200)

- [ ] Открыть `/admin` — dashboard рендерится, sidebar виден
- [ ] Открыть `/admin/tasks/new` — форма «Добавить URL»
- [ ] Открыть `/admin/discovered-urls`
- [ ] Открыть `/admin/discovered-urls?status=discovered` (и другие фильтры если есть)
- [ ] Открыть `/admin/editorial-queue`
- [ ] Кликнуть **Open** / ссылку на document из editorial — document detail 200
- [ ] Из discovered-urls открыть task (`/admin/tasks/{id}`) если есть enqueued row
- [ ] Пройти по **всем группам sidebar** — нет 404/500
- [ ] External: `/health`, `/health/ready`, `/docs` открываются в новой вкладке

### Функциональные POST (на staging / test URL)

- [ ] `/admin/tasks/new` — создать task с **тестовым URL** (не production publish)
- [ ] `/admin/discovered-urls` — Enqueue / Ignore **не изменили** action path (DevTools → form action)
- [ ] Editorial — кнопки RC/QC отправляют POST на прежние URLs
- [ ] Document detail — **не регрессировать** один POST (например run-quality) если страница уже трогалась

### Регрессия

- [ ] POST actions не изменены (сверка `action="/admin/..."` с inventory)
- [ ] Redirect после POST: task create → `/admin/tasks/{id}`; enqueue → task или discovered-urls
- [ ] Логи: `storage/logs/app.log` — нет новых ERROR/traceback после smoke
- [ ] `python scripts/smoke/check_health.py` — PASS
- [ ] `python scripts/smoke/run_all.py` — PASS (без `--include-production` если не нужно)
- [ ] `ruff check app/admin` — если ruff установлен в venv
- [ ] pytest — если появится в проекте (сейчас module not installed)

### Визуальная проверка

- [ ] Sidebar не перекрывает контент на 1280px и 1920px
- [ ] Wide table (discovered-urls) — horizontal scroll, не ломает layout
- [ ] Активный пункт меню соответствует текущему URL
- [ ] Формы readable: labels, inputs, submit button

---

## Rollback plan

1. **Git:** каждый этап — отдельный commit; rollback = `git revert <commit>` или `git checkout master -- app/admin/templates/base.html app/admin/static/admin.css`.
2. **Backup перед этапом 1:**
   ```bash
   cp app/admin/templates/base.html app/admin/templates/base.html.bak
   cp app/admin/static/admin.css app/admin/static/admin.css.bak
   ```
3. **Deploy:** перезапуск только app service (не nginx/postgres); см. `docs/DEPLOYMENT.md`.
4. **Критерий отката:** любой POST smoke fail, 500 на `/admin`, или broken layout на P0 страницах.
5. **Время отката:** < 5 мин (restore 2 файла + restart).

---

## Рекомендуемые команды после следующего этапа (этап 1 — layout)

На сервере `/opt/scrap`:

```bash
# Health
.venv/bin/python scripts/smoke/check_health.py

# Полный smoke (без production checks)
.venv/bin/python scripts/smoke/run_all.py

# Lint (если установлен ruff в venv)
.venv/bin/ruff check app/admin

# Ручная проверка admin (curl) — Scrap на порту 8800
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8800/admin
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8800/admin/tasks/new
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8800/admin/discovered-urls
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8800/admin/editorial-queue

# Логи после smoke
tail -50 storage/logs/app.log
```

---

## Связанные документы

- [admin-ui-routes-inventory.md](./admin-ui-routes-inventory.md) — полная таблица routes
- [ADMIN_UI.md](./ADMIN_UI.md) — функциональное описание страниц
- [SCRIPTS.md](./SCRIPTS.md) — smoke scripts

---

## Этап: detail operator clarity (2026-05-19)

- **Ветка:** `admin-ui-detail-operator-clarity` (от `master` после Batch 5)
- **Scope:** только `document_detail.html`, `release_candidate_detail.html`, `admin.css`, smoke scripts, docs
- **Результат:** сводка «Что сейчас» / «Следующий шаг»; блокировки с пояснениями; debug в `<details>`; smoke markers
- **Закрыто:** дубль h1 на RC detail; визуальный шум raw-текстов
- **Debt:** Media duplicate (свёрнут); полный i18n raw enum; выравнивание publish history table

---

## Следующий промпт (рекомендация)

**Этап 2 — UI kit:** новая ветка `admin-ui-kit-stage-2`; scope `admin.css` + optional `_ui_macros.html`; унификация кнопок, табов, таблиц, бейджей; без правок POST/forms/routes.
