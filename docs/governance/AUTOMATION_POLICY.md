# Automation Policy — Scrap

Политика автоматизации: scheduler, `automation_rules`, enrichment jobs, и **Target** Stage 5 batch generation. **Current** defaults — safe/off.

## Production defaults (Current)

| Flag / состояние | Default | Смысл |
|------------------|---------|--------|
| `ENABLE_SCHEDULER` | `false` | `scrap-scheduler` не выполняет ticks |
| `ENABLE_AUTOMATION` | `false` | Rules не запускаются автоматически |
| `ENABLE_AUTO_PUBLISH` | `false` | Нет auto publish draft/public |
| Automation rules in DB | often `disabled` | Ручное enable после review |

**Truth:** при `ENABLE_AUTOMATION=true` rule type `enqueue` **может** auto-enqueue discovered URLs (quality-gated). Policy «no auto enqueue» = **только пока automation off**. См. [CONSOLIDATION_INVENTORY.md](../CONSOLIDATION_INVENTORY.md).

**Required:** любое включение automation — осознанное действие оператора + запись в ops log / PROJECT_LOG.

## Trust levels

Уровень задаётся **per project** (Target: поле/профиль проекта). Пока — политика; реализация trust level в коде может быть частичной.

| Level | Генерация | Quality / RC | Draft publish | Public publish |
|-------|-----------|--------------|---------------|----------------|
| **0** | Allowed (в рамках лимитов) | Manual | **Forbidden** auto | **Forbidden** |
| **1** | Allowed | Auto quality/RC **создание** | **Forbidden** auto; operator approval **Required** | **Forbidden** |
| **2** | Allowed | Auto после policy checks | **Allowed** auto draft **после** gates | **Forbidden** |
| **3** | Allowed | Auto | Auto draft | **Target only**: отдельный feature flag + strong gates + explicit operator enable |

| | |
|---|---|
| **Current** | Publish draft **не автоматизируется**; production path — operator approve RC → manual `publish-draft`. Automation/scheduler по умолчанию **off**. Фактическое поведение ближе к **Level 0–1**. |
| **Target Level 2** | Auto-draft **может** быть разрешён только после прохождения policy gates (см. ниже) и `project.trust_level >= 2`. |
| **Forbidden** | Public publish до **Level 3** + отдельного feature flag + explicit operator enablement (PUBLISH_POLICY). |
| **Forbidden** | Level 3 без отдельного approved implementation stage. |
| **Forbidden** | Auto-public publish по умолчанию на любом уровне. |

### Current vs Target — publish и editorial

| Действие | Current | Target |
|----------|---------|--------|
| Publish draft | **Manual** — operator approve RC, затем publish | **Level 2:** auto-draft только через **policy-approved RC path** (все gates + audit) |
| Public publish | **Forbidden** из automation | **Level 3 only** + отдельный flag; до этого **Forbidden** |
| Editorial approve | **Manual** — оператор | **Level 2+:** auto-approval RC **только** отдельной policy и при `trust_level >= 2`; не по умолчанию |

## Обязательные gates (перед auto draft / auto RC)

Все проверки должны быть **детерминированы или audit-logged**; сбой gate = stop, не silent skip.

| Gate | Current / Target |
|------|------------------|
| Brief exists | **Target** (Stage 5); для scraped — N/A |
| Quality score ≥ project threshold | **Current** при `ENABLE_QUALITY_REVIEW` |
| RC QA score ≥ threshold | **Current** (release candidate QA) |
| No critical duplicate / cannibalization | **Current** warnings; critical block — policy per project |
| Daily / hourly limits | **Current** scheduler/automation limits |
| Retry limits | **Current** publish retry, enrichment, automation runs |
| Project trust level | **Target Level 2+:** `trust_level >= 2` обязателен для auto-draft; **Current** — implicit via flags |
| Audit trail | **Required** — `automation_runs`, `pipeline_events`, `llm_runs` |

**Target Level 2** — auto-draft допустим только если одновременно: brief exists (Stage 5) или N/A для scraped; quality ≥ threshold; RC QA ≥ threshold; no **critical** duplicate/cannibalization; daily/hourly limits; `trust_level >= 2`; полный audit trail.

### Manual gates

| Gate | Current | Target |
|------|---------|--------|
| Publish draft | **Manual** — operator approve RC, затем publish | **Level 2:** may automate draft publish **only** through policy-approved RC path (gates выше) |
| Publish public | **Forbidden** в automation | **Forbidden** до Level 3 + отдельного feature flag |
| Editorial approve / reject | **Manual** | **Level 2+:** auto-approval RC только **отдельной policy** и при `trust_level >= 2` |
| Media asset final approval | **Manual** (operator) | **Manual** unless future explicit policy |
| Force bypass | **Forbidden** без HUMAN_OVERRIDE_POLICY | Same |

См. также ARCHITECTURE §4A (historical «не автоматизировать» editorial/publish — уточнено здесь для Target Level 2).

## Scheduler и automation runs (Current)

- `scrap-scheduler`: locks, heartbeat, stale recovery.
- `POST /api/automation/rules/{id}/run` → `automation_run` queued; cancel/mark-failed supported.
- Enrichment tick **before** automation tick; isolated limits.
- Worker: scraping batch **first**, max 1 enrichment job per poll.

## Stage 5 automation (Target)

Topic batches → brief → article → (optional) media:

| | |
|---|---|
| **Target** | Batch limits: max topics per batch, max articles per day per project. |
| **Target** | Kill switch: env + admin disable all rules + cancel queued runs. |
| **Forbidden** | Mass generation без batch caps. |
| **Forbidden** | Autonomous topic loops (discover → enqueue → scrape → generate без ceiling). |

## Forbidden (глобально)

| | |
|---|---|
| **Forbidden** | Auto-public publish по умолчанию. |
| **Forbidden** | Automation без kill switch (`ENABLE_AUTOMATION=false`, disable rules, cancel runs). |
| **Forbidden** | Celery/Redis «fire and forget» без audit (не текущий дизайн). |
| **Forbidden** | Обход `needs_revision` / `rejected` scheduler-ом без `force` + audit. |

## Required

| | |
|---|---|
| **Required** | `automation_runs` + `progress_json` / `logs_json` для видимости оператору. |
| **Required** | Per-rule hourly/daily + global hourly + max concurrent runs. |
| **Required** | Source discovery: **no auto enqueue** (manual enqueue only). |

## Связь с feature flags

| Flag | Automation impact |
|------|-------------------|
| `ENABLE_SOURCE_DISCOVERY` | Discovery only; no auto pipeline enqueue |
| `ENABLE_PUBLISHING` | Разрешает publish **механизм**, не auto |
| `ENABLE_AUTO_PUBLISH` | Must stay **false** until PUBLISH_POLICY approved stage |
| `ENABLE_HERMES` | Optional; не включает auto loops |

## Открытые вопросы

- Где хранить `project.trust_level` (DB column vs project profile JSON).
- Единый «automation policy version» в `automation_rules.metadata`.
- SLA на stale `running` automation runs vs enrichment jobs.
