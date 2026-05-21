# Scrap Platform Roadmap

<!--
CURRENT ROLE: canonical execution roadmap (phase order, tracks, next tasks).
NOT: runtime implementation contract | historical shipped log | full architecture.
CANONICAL OWNERSHIP: docs/CANONICAL_OWNERSHIP.md
-->

**Canonical execution map** для разработки и ops. Объединяет [MASTER_PLAN.md](MASTER_PLAN.md), [PROJECT_LOG.md](PROJECT_LOG.md), [governance/](governance/README.md), [adr/](adr/README.md), [ARCHITECTURE.md](ARCHITECTURE.md).

**Legend:**

| Label | Meaning |
|-------|---------|
| **IMPLEMENTED** | В production runtime сейчас |
| **CURRENT** | Фактическое поведение / зрелость |
| **TARGET** | Целевое состояние (может быть не в коде) |
| **PROPOSED** | ADR или фаза, не утверждена / не начата |

**Constraints (не менять без explicit phase):** pipeline semantics, CRMFlow24 draft-only publish, Hermes/CLIProxyAPI repos untouched, automation off by default.

---

## 1. Current platform maturity

| Dimension | CURRENT | Notes |
|-----------|---------|-------|
| **Runtime** | Stage **4V+** **IMPLEMENTED** | Scrape → rewrite → RC → draft CRMFlow24; strategy 4G–4K; RC QA 4L; pilot 4S–4V |
| **Governance** | Iterations **1–3** **IMPLEMENTED** (docs) | 17 policy files; runtime alignment **Phase A–D shipped** (2026-05-20) |
| **Automation** | Trust **Level 0–1** **CURRENT** | `ENABLE_SCHEDULER=false`, `ENABLE_AUTOMATION=false`, manual publish |
| **Production mode** | **Manual-first** **CURRENT** | Operator approve RC, quality manual-first, no auto-public |
| **Stage 5** | **TARGET** only | Content Studio — **governance-only**, нет runtime |
| **Hermes** | Optional **IMPLEMENTED** (default off) | Модуль в Scrap; pipeline **не** зависит |

### Production constraints (CURRENT)

- Publish: draft webhook → CRMFlow24 only ([PUBLISH_POLICY](governance/PUBLISH_POLICY.md))
- `ENABLE_AUTO_PUBLISH=false` **REQUIRED**
- Source discovery: no auto-enqueue **while automation off** (enqueue rule exists if automation enabled)
- All LLM via CLIProxyAPI from Scrap (не модифицировать cliproxy)
- Governance = source of truth для policy; code = source of truth для behavior

---

## 2. Strategic tracks

### Track A — Core Pipeline

| | |
|---|---|
| **Goal** | Надёжный scrape → parse → clean → rewrite → SEO → save |
| **Status** | **IMPLEMENTED** (4V+) |
| **Blockers** | Domain parsers; occasional `failed_retryable` on LLM |
| **Direction** | Hardening, parser coverage, idempotent worker |

### Track B — Governance & Runtime Alignment

| | |
|---|---|
| **Goal** | Policy ↔ code parity; invariant enforcement |
| **Status** | Phase A enforcement **IMPLEMENTED**; trust **engine** — TARGET |
| **Blockers** | ADR-002 accept; `min_trust` on rules; RC auto-invalidate in DB |
| **Direction** | [ENFORCEMENT_MATRIX](governance/ENFORCEMENT_MATRIX.md); [CONSOLIDATION_INVENTORY.md](CONSOLIDATION_INVENTORY.md) |

### Track C — Admin UX

| | |
|---|---|
| **Goal** | Operator clarity, RU labels, high-risk pages safe |
| **Status** | **IMPLEMENTED** partial (admin redesign batches) |
| **Blockers** | RC/menu visibility; enum display debt |
| **Direction** | Visibility for queue/trust/incidents (Phase B) |

### Track D — Automation & Scheduler

| | |
|---|---|
| **Goal** | Controlled automation with kill switch |
| **Status** | **IMPLEMENTED** infra (4A–4B); **CURRENT** disabled |
| **Blockers** | trust_level, policy_version on rules |
| **Direction** | Automation hardening (TARGET) before enablement |

### Track E — Content Studio / Stage 5

| | |
|---|---|
| **Goal** | Topic → brief → outline → generated article |
| **Status** | **TARGET** — [STAGE5_CONTENT_STUDIO](governance/STAGE5_CONTENT_STUDIO.md) |
| **Blockers** | ADR-001/002; schema; provenance validator |
| **Direction** | Stage 5 foundation (TARGET) after trust engine + ADR-001 |

### Track F — Analytics & Intelligence

| | |
|---|---|
| **Goal** | Post-publish feedback, campaigns, canonical intelligence |
| **Status** | **IMPLEMENTED** 4K–4R (manual import); deterministic-first |
| **Blockers** | No live GA; manual snapshots |
| **Direction** | Read-only insights; no auto strategy loops |

### Track G — Reliability & Operations

| | |
|---|---|
| **Goal** | Backups, smoke, rollback discipline, retention |
| **Status** | **IMPLEMENTED** partial (3C, 4O–4P) |
| **Blockers** | Automated retention jobs; queue metrics |
| **Direction** | Phase B–C ops visibility |

### Track H — AI Orchestration

| | |
|---|---|
| **Goal** | Typed LLM contracts, prompt lifecycle, optional Hermes |
| **Status** | CLIProxy **IMPLEMENTED**; prompts DB **IMPLEMENTED**; Hermes connector **IMPLEMENTED** off |
| **Blockers** | Prompt experiment framework **TARGET** |
| **Direction** | [PROMPT_LIFECYCLE_POLICY](governance/PROMPT_LIFECYCLE_POLICY.md); Hermes via API only |

---

## 3. Runtime maturity model

Платформенная зрелость (не путать с project `trust_level` 0–3).

| Level | Name | Requirements | Automation | Forbidden |
|-------|------|--------------|------------|-----------|
| **0** | MVP | Single URL task, mock rewrite | Off | Production publish |
| **1** | Stable manual ops | Full pipeline, RC QA, CRMFlow24 draft, governance docs | Off default; manual publish | Auto-public |
| **2** | Controlled automation | Phase A shipped; trust **engine** + rule `min_trust` | Scheduler/rules **opt-in**; L0–1 only | Auto-draft without gates |
| **3** | Multi-project production | Per-project trust, caps, queue metrics | L2 auto-draft **TARGET** | Level 3 auto-public |
| **4** | Generated content platform | Stage 5 phases D–E; provenance enforced | Bounded generation batches | Fake scrape URLs |
| **5** | Bounded orchestration | Hermes chains optional; full observability | L3 **PROPOSED** only with ADR-003 | Autonomous loops |

**CURRENT platform maturity:** **Level 1** only. Phase A снял часть governance gaps; **Level 2 требует** trust rule engine и осознанное включение automation — не достигнут.

**Operational expectations at CURRENT:**

- Operator in loop for publish and editorial
- Incidents handled via [OPERATOR_RUNBOOK](governance/OPERATOR_RUNBOOK.md)
- Governance changes precede automation enablement

---

## 4. Phase execution order

**Naming note:** буквы A–D ниже — **shipped alignment phases** (2026-05-20). Отдельно: **Automation hardening** и **Stage 5 foundation** — TARGET, без буквенной путаницы.

### Shipped — governance ↔ runtime alignment (IMPLEMENTED)

| Phase | Scope | Status |
|-------|--------|--------|
| **A** | `validate_revision_current_for_publish`, `force_reason`, `operator_touched`, `projects.trust_level` (visibility), governance smoke | **IMPLEMENTED** (migration 026) |
| **B** | `/admin/diagnostics`, `GET /api/ops/diagnostics`, queue/publish/trust visibility | **IMPLEMENTED** |
| **C** | Diagnostics bounds, localhost API guard, incident triage, severity labels | **IMPLEMENTED** |
| **D** | `operational_snapshots` bounded history (migration 027) — **not** Stage 5 | **IMPLEMENTED** |

**Consolidation (truth alignment, 2026-05-21):** docs/runtime/governance sync — см. [CONSOLIDATION_INVENTORY.md](CONSOLIDATION_INVENTORY.md), `PROJECT_LOG.md`. **No new runtime features.**

**Must remain:** `ENABLE_AUTOMATION=false`, `ENABLE_SCHEDULER=false`, `ENABLE_AUTO_PUBLISH=false` by default.

### Target — not started

| Track | Scope |
|-------|--------|
| **Automation hardening** | `min_trust` on rules, queue caps, cost caps, retention jobs — [QUEUE_AND_CAPACITY_POLICY](governance/QUEUE_AND_CAPACITY_POLICY.md) |
| **Trust engine** | ADR-002 accept; promotion audit; rule engine reads `projects.trust_level` |
| **Stage 5 foundation** | ADR-001; topic/brief schema; provenance validator — [STAGE5_CONTENT_STUDIO](governance/STAGE5_CONTENT_STUDIO.md) |
| **Controlled generation** | Bounded batches; auto-draft RC path only (ADR-003); **Forbidden:** auto-public |

Historical stage map (IMPLEMENTED): [MASTER_PLAN.md](MASTER_PLAN.md) (4G–4V).

---

## 5. Current vs Target matrix

| Area | Current | Target | Status |
|------|---------|--------|--------|
| **Publish** | Draft → CRMFlow24; manual RC approve | Same + optional L2 auto-draft | **IMPLEMENTED** / auto-draft **PROPOSED** |
| **Automation** | Infra yes; defaults off | Trust-gated rules, caps | **IMPLEMENTED** off / **TARGET** on |
| **Trust** | Column + visibility (L0 default) | DB + audit + rule engine | **IMPLEMENTED** column / **TARGET** engine |
| **AI orchestration** | CLIProxy + DB prompts | + experiment framework | **IMPLEMENTED** partial |
| **Generated content** | None | Stage 5 pipeline | **TARGET** |
| **RC QA** | Deterministic QA pack | + generated payload checks | **IMPLEMENTED** / extend **PROPOSED** |
| **Analytics** | Manual snapshot import | Richer dashboards | **IMPLEMENTED** manual |
| **Rollback** | CRMFlow24 manual | + runbooks automated assist | **IMPLEMENTED** doc / **TARGET** tooling |
| **Scheduler** | Single lock, cancel API | Metrics + DLQ | **IMPLEMENTED** partial |
| **Provenance** | Scraped + llm_runs | + generated `source.type` | **IMPLEMENTED** partial |

---

## 6. Governance alignment backlog

Policy exists; runtime partial or missing.

| Policy | Doc | Runtime status | Priority | Risk |
|--------|-----|----------------|----------|------|
| trust_level rule engine | TRUST_POLICY, ADR-002 | column only; **governance-only** for gating | **P0** | critical |
| trust never auto-up | TRUST_POLICY | governance-only | P1 | high |
| auto demotion | TRUST_POLICY | governance-only | P2 | medium |
| operator_touched | HUMAN_OVERRIDE, H2 | **partially enforced** (automation skip) | P1 | medium |
| force_reason | HUMAN_OVERRIDE, A6 | **enforced** (new publishes); force still bypasses gates | P1 | high |
| stale revision at publish | C4 | **fully enforced** (all publish paths) | — | — |
| RC auto-invalidate on revision change | C4 | governance-only (publish blocks; approve may lag) | P1 | high |
| generated provenance | PROVENANCE, C5/C6 | planned (Stage 5) | P1 | critical |
| Level 2 auto-draft | AUTOMATION, ADR-003 | planned | P2 | high |
| M4 no auto-enqueue | AUTOMATION | **enforced only if automation off** | P0 if automation on | high |
| queue caps / DLQ | QUEUE_POLICY | partial limits | P2 | high |

**Alignment rule:** trust engine + automation hardening before `ENABLE_AUTOMATION=true`.

---

## 7. Execution principles

| Principle | Implication |
|-----------|-------------|
| Incremental evolution only | No big rewrite; small PRs per task |
| Immutable revisions | New version = new row |
| Manual-first production | Automation opt-in per project |
| No hidden automation | Rules visible; kill switch documented |
| No autonomous publish | AI recommends; operator/policy gates publish |
| Governance before automation scaling | Shipped Phase A + trust engine before automation enablement |
| Auditability over speed | llm_runs, publish_runs, automation_runs retained |
| Bounded AI only | Caps, trust, no infinite loops |
| Dangerous changes behind flags | New behavior default **off** |
| Hermes/CLIProxy untouched | Scrap integrates via API/env only |

---

## Next Recommended Runtime Tasks

**After Consolidation (docs truth):** не расширять automation/Stage 5 до закрытия trust engine.

### Critical (before automation)

| Task | Why | Risk |
|------|-----|------|
| Accept ADR-002 + trust rule engine | Column alone is decorative | critical |
| `automation_rules.min_trust_level` | M4 when automation on | high |
| RC auto-invalidate in DB on revision change | Approve on stale RC still possible | high |

### High

| Task | Why | Risk |
|------|-----|------|
| Automation hardening (queue/cost caps) | Runaway prevention | high |
| Accept ADR-001 before Stage 5 schema | Provenance model | high |
| Commit/deploy discipline on hermes | Uncommitted Phase A–D tree breaks smoke `git_clean` | medium |

### Forbidden without explicit approval

| Task | Why |
|------|-----|
| `ENABLE_AUTOMATION=true` at scale | No trust engine |
| Stage 5 runtime | ADR-001 not accepted |
| Auto-public | ADR-003, PUBLISH_POLICY |

---

## Document map

| Question | Read first |
|----------|------------|
| What to build next? | **This file** §4, §Next tasks |
| What is implemented? | [MASTER_PLAN.md](MASTER_PLAN.md), [PROJECT_LOG.md](PROJECT_LOG.md) |
| What must never happen? | [governance/SYSTEM_INVARIANTS.md](governance/SYSTEM_INVARIANTS.md) |
| How to operate today? | [governance/OPERATOR_RUNBOOK.md](governance/OPERATOR_RUNBOOK.md) |
| How system is built? | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Undecided design? | [adr/](adr/README.md) |

**New work entrypoint:** update ROADMAP phase status → implement behind flag → PROJECT_LOG → ENFORCEMENT_MATRIX row.
