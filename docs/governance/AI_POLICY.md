# AI Policy — Scrap

Политика AI-агентов и LLM-вызовов. **Current** = действует сейчас. **Target** = планируется (Stage 5+). **Forbidden** = запрещено. **Required** = обязательно.

## Принципы

| | |
|---|---|
| **Required** | Все production LLM-вызовы из Scrap идут через **CLIProxyAPI** (единая граница). |
| **Required** | Каждый значимый LLM-вызов оставляет след в **`llm_runs`** (audit). |
| **Required** | Явный `model` / model alias; без provider default (см. ARCHITECTURE §14). |
| **Forbidden** | Прямые вызовы LM Studio / OpenAI / провайдеров из worker/core в обход CLIProxyAPI. |
| **Forbidden** | Любой агент как **autonomous decision owner** (финальное решение о publish, editorial, bypass gates). |
| **Current** | **Hermes** — optional connector (`ENABLE_HERMES=false` default); pipeline **не** зависит; см. [ARCHITECTURE.md](../ARCHITECTURE.md) §12. |

## Допустимые роли агентов

Роль = тип задачи + prompt contract + ожидаемая схема ответа. Не отдельный «автономный бот».

### Current (реализовано или в активном использовании)

| Роль | Назначение | Автоматизация |
|------|------------|----------------|
| `reviewer` | LLM review после clean | Worker при `ENABLE_LLM_REVIEW`; иначе manual API |
| `rewriter` | Рерайт статьи | Worker при `REWRITER_PROVIDER=cliproxy` |
| `seo` | SEO metadata | Worker при `ENABLE_SEO_ENRICH`; иначе manual |
| `quality` | Quality scoring, verdict | **Manual-first** (`run-quality`); не блокирует worker rewrite |
| `topic_cleanup` | Опциональная очистка топиков (strategy) | Async enrichment; deterministic-first |

### Target (Stage 5 — Content Studio Automation, **не в production**)

| Роль | Назначение |
|------|------------|
| `brief_generator` | Brief по topic из batch |
| `outline_planner` | Структура статьи |
| `article_writer` | Generated draft |
| `image_prompt_generator` | Промпт для изображения |
| `image_generator` | Генерация media asset |

Добавление Target-ролей в runtime — только после отдельного approved этапа, trust policy и миграций/схем (см. CONTENT_MODEL, AUTOMATION_POLICY).

## Hermes

| | |
|---|---|
| **Current** | Scrap не импортирует код Hermes; не меняет `/hermes`. |
| **Target** | Оркестрация цепочек через явные API-контракты; всё равно через CLIProxyAPI для LLM. |
| **Forbidden** | Hermes как обязательная зависимость старта `scrap-api` / worker. |
| **Forbidden** | Вызов Hermes из fetch/parse/clean. |

## Что AI может делать автоматически

**Allowed (при включённых флагах и без обхода gates):**

- classify / extract / score (детерминированные и LLM enrichment в очереди);
- rewrite, SEO в worker pipeline;
- topic_cleanup в `llm_enrichment_jobs` (optional, isolated tick);
- рекомендации в JSON (risks, recommendations, QA warnings);
- создание **новой** `document_revision` при rerun (immutable snapshot).

**Не считается «решением»:** текст рекомендации, score, draft поля в metadata — до применения оператором или policy gate.

## Что требует policy или оператора

| Действие | Требование |
|----------|------------|
| Publish draft в CRMFlow24 | `ENABLE_PUBLISHING`, readiness, quality/editorial gates, **release candidate** path (см. PUBLISH_POLICY) |
| Editorial approve | Оператор; `ENABLE_EDITORIAL_WORKFLOW` |
| Обход `rejected` / `needs_revision` | `force` + audit (`publish_runs.force_used`, причина) |
| Включение automation rule | Оператор + `ENABLE_AUTOMATION` / scheduler |
| Auto-publish (любой вид) | **Forbidden** по умолчанию; см. AUTOMATION_POLICY Level 3 |
| Target: mass article generation | Trust level + batch limits + kill switch |

## Gates — AI не обходит

AI **не должен** самостоятельно:

- ставить `editorial_status=approved_for_publish` без workflow оператора;
- публиковать draft без прохождения release candidate QA (production path);
- подтверждать public publication в CRMFlow24;
- включать automation rules или scheduler;
- снимать canonical/cannibalization warnings как «resolved» без записи в audit.

Рекомендация AI ≠ выполненное действие, пока не зафиксированы DB-запись, `pipeline_event`, `llm_run` или operator action.

## Запрет self-generated infinite loops

| | |
|---|---|
| **Forbidden** | Циклы вида: generate → auto-publish → scrape own output → regenerate без лимитов. |
| **Forbidden** | Autonomous topic discovery loops (batch → topics → enqueue → scrape без caps). |
| **Required** | Retry limits, daily/hourly caps на automation и enrichment (см. AUTOMATION_POLICY). |
| **Required** | Scheduler/automation **disabled by default** (`ENABLE_SCHEDULER=false`, `ENABLE_AUTOMATION=false`). |

## Audit — llm_runs

**Required** для каждого LLM-вызова через production path:

- связь с `document_id` / `task_id` / job id где применимо;
- `prompt_template` или `key:version` из `prompt_service`;
- provider, model alias, upstream model, fallback flag;
- status, latency, error (без секретов в теле лога).

Admin: `/admin/llm-runs` — read-only аудит.

## Промпты

| | |
|---|---|
| **Current** | Active version из DB (`prompt_templates` / `prompt_versions`) + project override + code fallback. |
| **Required** | Версия промпта в audit (`llm_runs`). |
| **Forbidden** | «Тихое» изменение промпта без версии для уже одобренного RC. |

## Открытые вопросы (вне итерации 1)

- Единый registry «роль → model alias» в коде vs только docs.
- Максимальная длина chain при Target Stage 5 (brief → outline → article → media).
- Политика redaction PII в prompt context для generated content.
