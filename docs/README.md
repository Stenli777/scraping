# Документация Scrap

Индекс документации проекта Scrap (`/opt/scrap` на сервере hermes).

## Documentation authority

- **[CANONICAL_OWNERSHIP.md](CANONICAL_OWNERSHIP.md)** — кто canonical по каждому domain; порядок authority; anti-drift rules
- **[adr/ADR_LIFECYCLE.md](adr/ADR_LIFECYCLE.md)** — состояния ADR (proposed ≠ implement)

## Truth alignment

- **[CONSOLIDATION_INVENTORY.md](CONSOLIDATION_INVENTORY.md)** — force semantics, legacy paths, dead/decorative code (maintenance)

## Roadmap (execution)

- **[ROADMAP.md](ROADMAP.md)** — canonical execution map: maturity, tracks, shipped phases A–D, TARGET tracks, backlog

## Governance (политики)

Правила управления без изменения runtime. Индекс: [governance/README.md](governance/README.md).

**Итерация 1:** AI, content, automation, publish, provenance, human override.

**Итерация 2:** trust, invariants, Stage 5 design, operator runbook, ADR.

**Итерация 3 (runtime governance):**

- [governance/STATE_MACHINES.md](governance/STATE_MACHINES.md)
- [governance/ENFORCEMENT_MATRIX.md](governance/ENFORCEMENT_MATRIX.md)
- [governance/QUEUE_AND_CAPACITY_POLICY.md](governance/QUEUE_AND_CAPACITY_POLICY.md)
- [governance/ROLLBACK_POLICY.md](governance/ROLLBACK_POLICY.md)
- [governance/DATA_RETENTION_POLICY.md](governance/DATA_RETENTION_POLICY.md)
- [governance/PROMPT_LIFECYCLE_POLICY.md](governance/PROMPT_LIFECYCLE_POLICY.md)

Полный список policy-файлов — в [governance/README.md](governance/README.md).

## ADR (Architecture Decision Records)

- [adr/README.md](adr/README.md)
- [adr/ADR-001-generated-content-model.md](adr/ADR-001-generated-content-model.md) — **proposed**
- [adr/ADR-002-trust-level-storage.md](adr/ADR-002-trust-level-storage.md) — **proposed**
- [adr/ADR-003-auto-draft-vs-auto-public.md](adr/ADR-003-auto-draft-vs-auto-public.md) — **proposed**

## Архитектура и pipeline

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [SCRAPING_PIPELINE.md](SCRAPING_PIPELINE.md)
- [REWRITE_PIPELINE.md](REWRITE_PIPELINE.md)
- [API.md](API.md)
- [DATABASE.md](DATABASE.md)
- [DECISIONS.md](DECISIONS.md)

## Операции и интеграции

- [OPERATIONS.md](OPERATIONS.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [CRMFLOW24_INTEGRATION.md](CRMFLOW24_INTEGRATION.md)
- [RELEASE_RUNBOOK.md](RELEASE_RUNBOOK.md)
- [SECURITY.md](SECURITY.md)

## Admin UI

- [ADMIN_UI.md](ADMIN_UI.md)
- [admin-operator-workflow.md](admin-operator-workflow.md)

## Журнал

- [PROJECT_LOG.md](PROJECT_LOG.md)
