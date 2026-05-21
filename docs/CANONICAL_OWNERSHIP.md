# Canonical Documentation Ownership

## Purpose

Scrap has layered docs (roadmap, governance, ADR, architecture, log). Without explicit ownership, **duplicate truths** appear and LLM/agents cite the wrong file.

This document fixes:

- **which file wins** per domain;
- **authority order** on conflict;
- **update rules** to limit drift;
- **markers** for Current / Target / Historical.

**Not:** runtime contract — behavior is defined by code + env; docs describe and govern it.

---

## Authority order

On conflict, resolve in this order:

1. **Runtime behavior** — code in `/opt/scrap`, deployed env, DB state  
2. **Canonical doc** — table below (single owner per domain)  
3. **Governance policies** — `docs/governance/*` for «must/ must not»  
4. **Secondary references** — summaries and links only  
5. **Historical notes** — `PROJECT_LOG`, old ADR, deprecated sections  

**Rule:** If governance and runtime disagree → runtime is fact; governance is **target** until aligned ([ROADMAP.md](ROADMAP.md) Phase A).

---

## Canonical ownership table

| Domain | Canonical source | Secondary references | Notes |
|--------|------------------|----------------------|-------|
| Runtime roadmap & phase order | [ROADMAP.md](ROADMAP.md) | MASTER_PLAN, ARCHITECTURE §stages | ROADMAP wins for **what next** |
| Shipped stages (4G–4V) | [MASTER_PLAN.md](MASTER_PLAN.md) | PROJECT_LOG, ROADMAP §maturity | Historical **IMPLEMENTED** checklist |
| Runtime architecture | [ARCHITECTURE.md](ARCHITECTURE.md) | SCRAPING_PIPELINE, API.md | Not duplicate full pipeline in ARCHITECTURE |
| State machines (lifecycles) | [governance/STATE_MACHINES.md](governance/STATE_MACHINES.md) | SCRAPING_PIPELINE statuses | Link only; do not copy diagrams |
| Automation policy | [governance/AUTOMATION_POLICY.md](governance/AUTOMATION_POLICY.md) | ARCHITECTURE §4A–4B, OPERATIONS | |
| Publish policy | [governance/PUBLISH_POLICY.md](governance/PUBLISH_POLICY.md) | CRMFLOW24_INTEGRATION | |
| Trust policy | [governance/TRUST_POLICY.md](governance/TRUST_POLICY.md) | ROADMAP, AUTOMATION_POLICY | |
| Enforcement status | [governance/ENFORCEMENT_MATRIX.md](governance/ENFORCEMENT_MATRIX.md) | SYSTEM_INVARIANTS | Matrix = code↔policy map |
| System invariants | [governance/SYSTEM_INVARIANTS.md](governance/SYSTEM_INVARIANTS.md) | ENFORCEMENT_MATRIX | |
| Runtime ops history | [PROJECT_LOG.md](PROJECT_LOG.md) | — | **Immutable** log; not policy |
| ADR decisions | [adr/ADR-*.md](adr/README.md) + [DECISIONS.md](DECISIONS.md) when accepted | governance refs | See [ADR_LIFECYCLE.md](adr/ADR_LIFECYCLE.md) |
| Prompt lifecycle | [governance/PROMPT_LIFECYCLE_POLICY.md](governance/PROMPT_LIFECYCLE_POLICY.md) | ARCHITECTURE §prompts | |
| Rollback | [governance/ROLLBACK_POLICY.md](governance/ROLLBACK_POLICY.md) | OPERATOR_RUNBOOK | |
| Retention | [governance/DATA_RETENTION_POLICY.md](governance/DATA_RETENTION_POLICY.md) | BACKUP_AND_RECOVERY | |
| Queue & capacity | [governance/QUEUE_AND_CAPACITY_POLICY.md](governance/QUEUE_AND_CAPACITY_POLICY.md) | ARCHITECTURE worker order | |
| Stage 5 design | [governance/STAGE5_CONTENT_STUDIO.md](governance/STAGE5_CONTENT_STUDIO.md) | CONTENT_MODEL Target, ROADMAP Phase D–E | **TARGET only** |
| Doc authority meta | **This file** | governance/README | |
| Operator procedures | [governance/OPERATOR_RUNBOOK.md](governance/OPERATOR_RUNBOOK.md) | OPERATIONS, RELEASE_RUNBOOK | |
| Ownership index | **This file** | docs/README | |

---

## Duplicate truth policy

**Forbidden:**

- Copying full state machine diagrams into ARCHITECTURE, MASTER_PLAN, or ROADMAP  
- Duplicate roadmap phase lists outside ROADMAP (except brief link)  
- Restating publish semantics outside PUBLISH_POLICY + CRMFLOW24_INTEGRATION  
- Restating trust levels outside TRUST_POLICY + AUTOMATION_POLICY summary table  
- Treating PROJECT_LOG as current policy  

**Required instead:**

- One canonical section + markdown link  
- «See [canonical](path)» for details  

---

## Documentation update rules

| Change type | Update order |
|-------------|--------------|
| Runtime / API / pipeline | Code → canonical doc (API, PIPELINE, STATE_MACHINES) → ENFORCEMENT_MATRIX row → PROJECT_LOG |
| New policy | governance canonical file → ROADMAP backlog if needed → ADR if architectural |
| Shipped stage | MASTER_PLAN checkbox → PROJECT_LOG → ROADMAP maturity one-liner |
| ADR accepted | ADR state → DECISIONS.md → governance/ROADMAP references |
| Deprecation | Mark **Deprecated** in doc header; link replacement; do not delete history |

---

## Required markers

Use in doc headers and sections:

| Marker | Meaning |
|--------|---------|
| **Current** | Production fact or behavior today |
| **Target** | Planned; not in runtime |
| **Historical** | Past stages/logs; not active policy |
| **Deprecated** | Do not use for new work; link successor |
| **Governance-only** | Policy not fully enforced in code |
| **Partially enforced** | Some paths guarded |
| **Runtime enforced** | Code/API blocks or guarantees |
| **IMPLEMENTED** | Shipped and in prod |
| **PROPOSED** | ADR/phase not accepted |

---

## LLM / Cursor retrieval hints

1. «What to build next?» → `ROADMAP.md`  
2. «What is forbidden?» → `SYSTEM_INVARIANTS.md` + relevant `*_POLICY.md`  
3. «What was done on date X?» → `PROJECT_LOG.md`  
4. «How does X transition states?» → `STATE_MACHINES.md`  
5. «Is policy enforced?» → `ENFORCEMENT_MATRIX.md`  
6. «Undecided design?» → `adr/` + `ADR_LIFECYCLE.md`  

---

## Related

- [docs/README.md](README.md) — index  
- [governance/README.md](governance/README.md) — policy index  
- [.cursor/rules/canonical-doc-ownership.mdc](../.cursor/rules/canonical-doc-ownership.mdc)
