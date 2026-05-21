# Governance layer — Scrap

<!--
CURRENT ROLE: policy & invariants index (must/must not, Target vs Current).
NOT: execution roadmap | shipped history | runtime code contract.
CANONICAL FOR EXECUTION: ../ROADMAP.md
CANONICAL FOR ENFORCEMENT MAP: ENFORCEMENT_MATRIX.md
CANONICAL OWNERSHIP: ../CANONICAL_OWNERSHIP.md
-->

## Назначение

Каталог `docs/governance/` — **инженерный слой политик** для production AI content platform Scrap. Документы фиксируют:

- кто и что может решать (человек vs AI);
- какие сущности считаются source of truth;
- какие автоматизации допустимы и при каких trust levels;
- как публикуется контент и что запрещено по умолчанию;
- минимальные требования к provenance и audit trail.

**Итерация 1 (2026-05-20):** policy layer. **Runtime alignment Phase A–D shipped** — см. [ROADMAP.md](../ROADMAP.md) §4, [PROJECT_LOG.md](../PROJECT_LOG.md). **Consolidation (2026-05-21):** truth sync — [CONSOLIDATION_INVENTORY.md](../CONSOLIDATION_INVENTORY.md).

**Execution map (phases, tracks, runtime tasks):** [ROADMAP.md](../ROADMAP.md) — canonical entrypoint для новых этапов и alignment backlog.

**Doc authority:** [CANONICAL_OWNERSHIP.md](../CANONICAL_OWNERSHIP.md) · [ADR lifecycle](../adr/ADR_LIFECYCLE.md)

## Source of truth

| Область | Source of truth |
|--------|------------------|
| Кто canonical по domain | `docs/CANONICAL_OWNERSHIP.md` |
| Целевая политика (должно быть) | `docs/governance/*.md` |
| Execution order | `docs/ROADMAP.md` |
| Фактическая реализация | код в `/opt/scrap`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/DATABASE.md`, pipeline/ops docs |
| Операционные runbook | `docs/OPERATIONS.md`, `docs/RELEASE_RUNBOOK.md`, `docs/CRMFLOW24_INTEGRATION.md` |
| Журнал изменений | `docs/PROJECT_LOG.md` |
| Исторические MVP ADR | `docs/DECISIONS.md` (не путать с `docs/adr/`) |
| Truth / dead code inventory | `docs/CONSOLIDATION_INVENTORY.md` |

При конфликте:

- **governance** описывает **целевую** политику и границы (Current / Target / Forbidden / Required);
- **код и устаревшие docs** описывают **факт** на момент чтения;
- расхождение — сигнал к задаче на выравнивание (код, флаги, UI, docs), а не к «тихому» обходу gates.

## Governance ≠ runtime config

- Документы **не** подменяют `.env`, feature flags, `automation_rules`, nginx, systemd.
- Включение автоматизации или publish — только через существующие механизмы (env, admin, API) **и** в рамках политик ниже.
- Изменение политики: PR/review в `docs/governance/` + при необходимости запись в `docs/DECISIONS.md` и `docs/PROJECT_LOG.md`.

## Порядок чтения

1. [README.md](README.md) — этот файл  
2. [SYSTEM_INVARIANTS.md](SYSTEM_INVARIANTS.md) — глобальные инварианты (читать рано)  
3. [CONTENT_MODEL.md](CONTENT_MODEL.md) — сущности и immutable rules  
4. [PROVENANCE_MODEL.md](PROVENANCE_MODEL.md) — цепочка происхождения и audit  
5. [AI_POLICY.md](AI_POLICY.md) — роли агентов и LLM  
6. [TRUST_POLICY.md](TRUST_POLICY.md) — trust 0–3, promotion/demotion  
7. [AUTOMATION_POLICY.md](AUTOMATION_POLICY.md) — gates, kill switch  
8. [PUBLISH_POLICY.md](PUBLISH_POLICY.md) — draft vs public  
9. [HUMAN_OVERRIDE_POLICY.md](HUMAN_OVERRIDE_POLICY.md) — приоритет оператора  
10. [STAGE5_CONTENT_STUDIO.md](STAGE5_CONTENT_STUDIO.md) — **Target** design (не production)  
11. [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md) — чеклисты и emergency  
12. [STATE_MACHINES.md](STATE_MACHINES.md) — lifecycle сущностей  
13. [ENFORCEMENT_MATRIX.md](ENFORCEMENT_MATRIX.md) — policy → runtime enforcement  
14. [QUEUE_AND_CAPACITY_POLICY.md](QUEUE_AND_CAPACITY_POLICY.md) — очереди, лимиты, cost  
15. [ROLLBACK_POLICY.md](ROLLBACK_POLICY.md) — operational rollback  
16. [DATA_RETENTION_POLICY.md](DATA_RETENTION_POLICY.md) — хранение и cleanup  
17. [PROMPT_LIFECYCLE_POLICY.md](PROMPT_LIFECYCLE_POLICY.md) — версии промптов  

**ADR (proposed):** [docs/adr/](../adr/README.md)

**Итерация 3:** runtime governance — state machines, enforcement matrix, queues, rollback, retention, prompts.

Краткие ссылки: [ARCHITECTURE.md](../ARCHITECTURE.md), [SCRAPING_PIPELINE.md](../SCRAPING_PIPELINE.md), [CRMFLOW24_INTEGRATION.md](../CRMFLOW24_INTEGRATION.md).

## Документы каталога

| Файл | Фокус |
|------|--------|
| [AI_POLICY.md](AI_POLICY.md) | Роли AI, CLIProxyAPI, запрет автономных решений |
| [CONTENT_MODEL.md](CONTENT_MODEL.md) | Current pipeline + Target Stage 5 |
| [AUTOMATION_POLICY.md](AUTOMATION_POLICY.md) | Trust levels 0–3, gates, kill switch |
| [PUBLISH_POLICY.md](PUBLISH_POLICY.md) | Draft → CRMFlow24, запрет public из Scrap |
| [PROVENANCE_MODEL.md](PROVENANCE_MODEL.md) | Scraped / rewritten / generated / media / publish |
| [HUMAN_OVERRIDE_POLICY.md](HUMAN_OVERRIDE_POLICY.md) | Оператор важнее AI, force с audit |
| [TRUST_POLICY.md](TRUST_POLICY.md) | Trust 0–3, metrics, escalation |
| [SYSTEM_INVARIANTS.md](SYSTEM_INVARIANTS.md) | C/P/A/M/U/H invariants, forbidden states |
| [STAGE5_CONTENT_STUDIO.md](STAGE5_CONTENT_STUDIO.md) | Target Content Studio, phases 5A–5G |
| [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md) | Daily/pre-publish/emergency checklists |
| [STATE_MACHINES.md](STATE_MACHINES.md) | Task, document, RC, publish, automation states |
| [ENFORCEMENT_MATRIX.md](ENFORCEMENT_MATRIX.md) | Invariant enforcement status + gaps |
| [QUEUE_AND_CAPACITY_POLICY.md](QUEUE_AND_CAPACITY_POLICY.md) | Worker/scheduler queues, caps |
| [ROLLBACK_POLICY.md](ROLLBACK_POLICY.md) | Draft/revision/publish rollback |
| [DATA_RETENTION_POLICY.md](DATA_RETENTION_POLICY.md) | Retention, archive, secrets |
| [PROMPT_LIFECYCLE_POLICY.md](PROMPT_LIFECYCLE_POLICY.md) | Prompt versions, overrides |

## ADR

| ADR | Topic |
|-----|--------|
| [ADR-001](../adr/ADR-001-generated-content-model.md) | Generated storage model |
| [ADR-002](../adr/ADR-002-trust-level-storage.md) | trust_level storage |
| [ADR-003](../adr/ADR-003-auto-draft-vs-auto-public.md) | Auto-draft vs auto-public |

## Синхронизация

Копия governance должна существовать **локально** (репозиторий документации) и **на сервере** `/opt/scrap/docs/governance/`. Runtime читает governance только как справочник для людей и Cursor, не как конфиг при старте.

## Статус Stage 5

**Content Studio Automation** (topic batches, briefs, generated articles, media generation) — **future target**, не реализован в runtime. Упоминания в governance помечены как **Target**, не как Current.

## Known alignment tasks

| Задача | Статус |
|--------|--------|
| **trust_level** storage & audit | ADR-002 **proposed**; TRUST_POLICY written |
| **generated content** model | ADR-001 **proposed**; STAGE5 design doc |
| **Stage 5** schema & phases | STAGE5_CONTENT_STUDIO **Target** doc |
| **automation policy versioning** | Open — rule `policy_version` metadata |
| **data retention** | DATA_RETENTION_POLICY — ops automation **Target** |
| **Accept ADRs** | Move to `DECISIONS.md` when accepted |
| **ROLLBACK_POLICY** | Documented — CRMFlow24 public unpublish still manual |
| **Enforce invariants in code** | ENFORCEMENT_MATRIX — implement top gaps (stale RC, force reason) |
| **Prompt experiment framework** | PROMPT_LIFECYCLE — Target shadow tests |
| **Queue metrics dashboard** | QUEUE policy — Target observability |

По мере закрытия — `docs/DECISIONS.md`, `docs/PROJECT_LOG.md`.
