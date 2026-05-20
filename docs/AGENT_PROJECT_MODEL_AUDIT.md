# Agent / Project Model Audit (этап 4AD)

Дата: 2026-05-20. Окружение: `/opt/scrap` на `hermes`, read-only анализ кода и БД + скрипт `scripts/audit_agent_project_model.py`.

## Current database model

### Таблицы и поля (факт)

| Сущность | Таблица | Ключевые поля | Связь с проектом |
|----------|---------|----------------|------------------|
| Проект | `projects` | `id`, `slug`, `name`, `enabled`, … | — |
| Шаблон промпта | `prompt_templates` | `id`, `key` (**уникален глобально**), `name`, `task_kind`, `enabled` | **Нет `project_id`**. Шаблон всегда глобальный по ключу. |
| Версия промпта | `prompt_versions` | `prompt_template_id`, `version`, `content_md`, `is_active`, … | Нет `project_id`. «Глобально активная» версия — та, у которой `is_active=true` для шаблона. |
| Override проекта | `project_prompt_overrides` | `project_id`, `prompt_template_id`, `prompt_version_id`, `enabled` | **Единственная явная связь «проект ↔ шаблон (агент)»** в БД: какая версия применяется для проекта. |
| Запуск LLM | `llm_runs` | `project_id` (nullable), `task_id`, `prompt_template` (строка-ярлык), токены, … | Аудит использования; не источник истины для effective prompt. |

### Ограничения (PostgreSQL `information_schema`)

- `prompt_templates_key_key` — **UNIQUE** на `key` (глобальный каталог ключей).
- На `project_prompt_overrides` в миграции **007** нет UNIQUE `(project_id, prompt_template_id)` — теоретически возможны дубликаты строк; приложение должно опираться на сервисный слой (`get_project_override` + `.limit(1)`).

### Custom agent

- В БД это обычный `prompt_templates` с ключом **вне** `KNOWN_AGENT_KEYS` в `agent_registry`.
- **«Проектный» custom** в продуктовом смысле = существует `project_prompt_override` для пары `(project_id, prompt_template_id)` (создаётся из админки при custom + project).
- **«Глобальный» custom** = есть шаблон/версии, но **нет** override на конкретный проект — в пайплайн не подключается до явного использования в коде/override.

## Current service model

### `agent_registry.py`

- `AGENT_REGISTRY` задаёт метаданные для **пяти pipeline-ключей**: `review_article`, `rewrite_article`, `seo_enrich`, `quality_review`, `topic_cleanup_v1`.
- `KNOWN_AGENT_KEYS` = ключи реестра. **Custom-ключи в реестр не входят**; для них `get_agent_meta` возвращает fallback-лейблы (`stage=other` и т.д.).

### `prompt_service.py` — effective prompt resolution

1. Найти `PromptTemplate` по `key`; если нет или `enabled=false` → `code_fallback` (для неизвестных ключей — `ValueError` в fallback).
2. Если передан `project_id`, искать **включённый** `ProjectPromptOverride` для `(project_id, template.id)` и подставить связанный `PromptVersion`.
3. Иначе взять активную глобальную версию (`is_active=true`, последняя по `id`).
4. `ResolvedPrompt.source`: `project_override` если сработал override; иначе `global`; иначе `code_fallback`.
5. `template_ref`: `{key}:{version}#{source}` — удобно для логов/LLM audit.

**Замечание по краевому случаю:** если строка override есть, но `PromptVersion` «битая»/не совпадает с шаблоном, код откатывается на глобальную версию, но переменная `override` может остаться truthy — риск некорректного `source` в редком сценарии (для аудита зафиксировано; исправление вне scope 4AD при отсутствии симптома).

### `prompt_override_service.py`

- `get_project_override(db, project_id, key)` — только **enabled** override (`.enabled.is_(true)`).
- Создание/обновление версий override — через сервисные функции, вызываемые из админ-маршрутов.

### `agent_catalog_service.py`

- `get_global_agent_catalog` / `build_agent_catalog` — строки для **`/admin/agents`**: глобальные строки + строки по каждому включённому override проекта + custom-шаблоны.
- `get_project_agent_catalog(project_id)` — строки для **`/admin/projects/{id}/agents`**: все `KNOWN_AGENT_KEYS` + custom-шаблоны, у которых есть **хотя бы один** `project_prompt_override` для данного `project_id` (по `prompt_template_id`). **Не** подмешивает overrides других проектов.

## Current admin behavior

| URL | Источник данных | Фильтры |
|-----|-----------------|---------|
| `/admin/agents` | `build_agent_catalog` → `get_global_agent_catalog` | query: project / role / pipeline |
| `/admin/agents/new` | формы + POST create | создаёт версии и при необходимости override |
| `/admin/agents/{key}` | деталь шаблона + список overrides по всем проектам | глобальный контекст |
| `/admin/projects/{id}/agents` | `get_project_agent_catalog` | только текущий `project_id` |
| `/admin/projects/{id}/agents/{key}` | редактор override / effective | `project_id` + `key` |

### HTTP-проверка (`audit_agent_project_model.py --http`, 2026-05-20)

- `/admin/projects/4/agents` — **200**, маркер «Источник для этого проекта» присутствует, в HTML **нет** ссылок на чужие `/admin/projects/{id}/` кроме `4`.
- Ключи на странице проекта 4: 5 pipeline + несколько `zz_test_custom_4ab_*` — соответствует БД (override’ы тестового проекта 4).
- `/admin/agents` — ожидаемо содержит ссылки на проекты `1,3,4,5` (глобальный каталог).

## Effective prompt resolution (кратко)

Для пары `(project_id, agent_key)` effective = **override version** если override включён; иначе **глобальная активная версия**; иначе **fallback из кода** (для известных pipeline-ключей).

## What works correctly

- Глобальная уникальность `prompt_templates.key` — нет дублирования шаблонов по проектам.
- `project_prompt_overrides` однозначно выражает «проект использует конкретную версию шаблона».
- `get_active_prompt(..., project_id=)` — единая точка разрешения для рантайма.
- После 4AC: `get_project_agent_catalog` и project admin page **не** смешивают чужие проекты в scoped view.

## What is broken or confusing

1. **Продуктовая модель «агент» ≠ таблица «агенты»** — в БД только `prompt_templates` + overrides; оператор ищет сущность «project agent», её нет как отдельной строки — ощущение «нет привязки», хотя привязка выражена override’ом.
2. **Нет UNIQUE (project_id, prompt_template_id)** — риск дубликатов при гонках/ошибках; сейчас смягчается `limit(1)` в запросах.
3. **Custom без override** виден в глобальном каталоге, но не должен считаться «агентом проекта» до создания override — это правило UI/доков, не схемы.
4. **LLM audit string** `prompt_template` на `llm_runs` — человекочитаемо, но парсинг по префиксу `key:` хрупкий при смене формата (достаточно для текущих отчётов; опционально в будущем — отдельные столбцы `prompt_key`, `prompt_version`, `prompt_source`).

## Root cause of project agent leakage/confusion

- **Исторический UI-баг (до 4AC):** страница проекта перечисляла все non-registry `prompt_templates` без фильтра по `project_id`, из-за чего «утекали» custom других проектов.
- **Семантический разрыв:** оператор ожидает сущность «ProjectAgent», в БД есть только «глобальный шаблон + optional override» — без глоссария это выглядит как отсутствие связи.

## Options considered

### Option A — `prompt_templates` + `project_prompt_overrides` only

**Pros:** минимальная схема; уже реализовано; глобальный reuse шаблонов; один источник истины для effective prompt.  
**Cons:** нет отдельной строки «binding без смены версии» (но override можно включить/выключить); нужна дисциплина в UI и уникальное ограничение в БД по желанию.

### Option B — add `project_agent_bindings`

**Pros:** явная таблица «проект подключил агента»; можно хранить `enabled`, `notes` без привязки к конкретной версии.  
**Cons:** миграция + backfill + дублирование концепции с override; больше кода; риск рассинхрона «binding есть, override нет».

### Option C — `project_id` on `prompt_templates`

**Pros:** кажется «просто».  
**Cons:** ломает reuse одного шаблона в нескольких проектах; дубли ключей или сложные правила; **не рекомендуется**.

## Recommended decision

**Вариант A** — оставить текущую модель данных: глобальные `prompt_templates` + `project_prompt_overrides` как **единственная** связь agent→project для операторских промптов.

Custom project agent = **глобальный** `prompt_template` + **override** на проект (как сейчас). Глобальный custom без override не показывать на project page (правило каталога — уже в 4AC).

## Next implementation stage (после аудита)

1. **Опционально:** миграция `UNIQUE (project_id, prompt_template_id)` на `project_prompt_overrides` + очистка дубликатов, если они есть.
2. **Операторский слой:** в `ADMIN_UI.md` / подсказках явно писать: «Привязка к проекту = запись в `project_prompt_overrides`».
3. **Наблюдаемость:** при необходимости расширить `llm_runs` отдельными полями key/version/source **только** если отчётность/аналитика требует SQL без парсинга строки.
4. **Не делать** без отдельного ТЗ: `project_agent_bindings`, `project_id` на шаблонах, большой рефакторинг.

## Tests to protect behavior

- `scripts/test_project_agent_scoping.py` — изоляция проектов A/B.
- `scripts/check_project_agent_admin.py` — HTTP-маркеры scoped-страницы.
- `scripts/audit_agent_project_model.py` — read-only снимок БД + опционально `--http`.

## Приложение: snapshot project #4 (сервис)

На момент аудита `get_project_agent_catalog(db, 4)` возвращает **9** строк: 5 pipeline + 4 custom-ключа с override для проекта 4 (тестовые `zz_test_custom_4ab_*`). Это **ожидаемо** при наличии данных тестов; для «чистого» проекта останутся только 5 pipeline до первого override/custom.
