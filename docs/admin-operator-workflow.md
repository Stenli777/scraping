# Как работать в Scrap Admin

Операторский маршрут: от URL до публикации. В sidebar админки пункты **1–4** — основной pipeline; ниже — диагностика, качество/медиа, LLM и организация.

## Главный маршрут оператора

### 1. Добавить URL вручную

- **Страница:** `/admin/tasks/new`
- **Когда использовать:** если есть конкретная статья или страница для парсинга.
- **Дальше:** откроется карточка задачи `/admin/tasks/{id}` — проверьте статус, ошибки, документ и pipeline summary.

### 2. Запустить discovery

- **Страница:** `/admin/source-directories`
- **Когда использовать:** если нужно найти новые URL из каталогов источников (обход сайта/раздела).
- **Дальше:** после запуска discovery перейдите в **Найденные URL** (`/admin/discovered-urls`).

### 3. Разобрать найденные URL

- **Страница:** `/admin/discovered-urls`
- **Действия:** в очередь, игнор, фильтры по статусам.
- **Дальше:** задача или документ; при сбоях — `/admin/failed-items`.

### 4. Редактура

- **Страница:** `/admin/editorial-queue`
- **Что делать:** review, SEO, QC; подготовка к публикации.
- **Дальше:** release candidate — `/admin/release-candidates`.

### 5. Release candidates

- **Страница:** `/admin/release-candidates` → `/admin/release-candidates/{id}`
- **Detail:** операторские блоки «Что сейчас», «Следующий шаг», «Блокирующие проблемы» на карточке RC.

### 6. Публикации

- **Страница:** `/admin/publications` → `/admin/publications/{id}`
- **Что смотреть:** draft / public URL, статус, видимость.

## Sidebar (гибрид)

| Группа | Назначение |
|--------|------------|
| Обзор | дашборд, сбои |
| 1. Импорт | tasks/new, manual URLs |
| 2. Discovery | источники, discovered, quality источников |
| 3. Редактура | review, editorial-queue, drafts, RC list |
| 4. Публикация | targets, runs, publications, analytics, pilots |
| Диагностика | operations, system, pipeline-events |
| Качество и медиа | quality scores, canonical, media, enrichment |
| LLM и промпты | prompts, runs, smoke, Hermes |
| Организация / справка | projects, automation, settings, health, API docs |

## Служебные страницы

Используйте при диагностике, не на каждом проходе pipeline: LLM Runs, Pipeline Events, Prompts, Settings, System, Automation, Media/Enrichment jobs.

## Что делать при ошибках

1. `/admin/failed-items`
2. Карточка задачи или документа
3. `storage/logs/app.log` (без секретов в отчётах)
4. Не force publish без проверки блокировок

## Глоссарий статусов (кратко)

| Статус | Значение |
|--------|----------|
| `discovered` | URL найден discovery |
| `enqueued` | URL в scrape-очереди |
| `ignored` | Исключён оператором |
| `duplicate` | Дубликат URL |
| `done` | Задача успешно завершена |
| `error` | Ошибка задачи |
| `needs_review` | Ждёт редакторской проверки |
| `ready_to_publish` | Готов к RC / публикации |

---

См. также: [admin-ui-redesign-plan.md](./admin-ui-redesign-plan.md), [PROJECT_LOG.md](./PROJECT_LOG.md).
