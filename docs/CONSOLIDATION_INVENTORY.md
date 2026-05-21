# Consolidation Inventory — Scrap

<!--
CURRENT ROLE: truth-alignment artifact (dead code, force semantics, decorative systems).
NOT: execution roadmap | governance policy | runtime contract.
CANONICAL FOR EXECUTION: ROADMAP.md
CANONICAL FOR ENFORCEMENT: governance/ENFORCEMENT_MATRIX.md
-->

**Status:** maintenance reference (Consolidation Phase, 2026-05-21).  
**Purpose:** честная карта того, что реально работает, что декоративно, и что опасно при неправильной эксплуатации.

---

## 1. Production maturity (honest)

| Claim | Reality |
|-------|---------|
| «Production-ready platform» | **Manual-first pipeline** на одном сервере — **да** |
| «Level 2 controlled automation» | **Нет** — automation/scheduler off; trust column **не управляет** поведением |
| «Governance enforced» | **Частично** — publish/stale/force_reason/operator_touched; trust engine **нет** |
| «Stage 5 / Content Studio» | **Governance-only** — нет schema/runtime |
| «Hermes orchestration» | **Optional module, default off** — не «future-only» |

**Effective maturity:** **Level 1** (stable manual ops). См. [ROADMAP.md](ROADMAP.md) §3.

---

## 2. Force publish semantics (`force=true`)

Источник: `app/publishers/validators.py`, `app/services/publish_service.py`.

### Bypasses (gates отключены)

| Gate | Field / check | Risk class |
|------|---------------|------------|
| Duplicate successful publish | `find_duplicate_publish_run` | **Acceptable** — ops retry |
| Review take/score | `validate_review_for_publish` | **Dangerous** — слабый контент |
| Quality verdict/score/spam | `validate_quality_for_publish` | **Dangerous** — QC skip |
| Editorial status / `approved_for_publish` | `validate_editorial_for_publish` | **Dangerous** — editorial skip |

### Not bypassed (остаются)

| Check | Location |
|-------|----------|
| `ENABLE_PUBLISHING` / `ENABLE_AUTO_PUBLISH` | `_validate_preconditions` |
| `rewritten_text`, SEO slug | preconditions |
| Stale revision | `validate_revision_current_for_publish` |
| `force_reason` non-empty | `_validate_force_override` |

### Governance note

`force_reason` — **audit**, не **safety**. Политика: [HUMAN_OVERRIDE_POLICY.md](governance/HUMAN_OVERRIDE_POLICY.md). Admin (Runtime Safety): legacy form в `<details>`; checkbox `force_confirm`; подсветка force runs в `/admin/publish-runs`.

---

## 3. Legacy / deprecated surfaces

| Surface | Status | Risk | Mitigation |
|---------|--------|------|------------|
| `POST /api/documents/{id}/publish-draft` | **Deprecated** — RC-first | Skips RC QA discipline | Admin warn-box; OPERATIONS RC path |
| Admin document «Опубликовать черновик» | Same | Same | Legacy `<details>` + `force_confirm` + `op_error` banner |
| RC approve on stale revision | **Fixed (Runtime Safety)** | Was publish-only block | Service + admin disabled buttons |
| `POST /api/release-candidates/{id}/publish-draft` | **Preferred** | Lower | OPERATOR_RUNBOOK |
| Pilot `next_action` strips quality when RC approved | **UX only** | Misleading guidance | Documented; publish gates unchanged |
| `lm_studio` rewriter file | **Dead** — not in `registry.py` | Config confusion | REWRITE_PIPELINE note |
| `ENABLE_CAMPAIGN_PLANNING` in `.env.example` | **Unwired** | False expectation | Comment in example |
| `domain_trust_registry.trust_level` | **Active** (source quality) | Confusion with `projects.trust_level` | Diagnostics note |

---

## 4. Dead / decorative complexity inventory

| Item | Verdict | Recommendation |
|------|---------|----------------|
| `app/rewriters/lm_studio_rewriter.py` | Dead provider | **Deprecate** — doc only; remove later |
| 73× `app/services/*` | Many peripheral | **Keep** — mark non-core in this file |
| Campaign/canonical/cluster APIs | Partially used | **Keep** — not daily ops path |
| `operational_snapshots` | Bounded visibility | **Keep** — not metrics platform |
| `operational_incidents` | Bounded incident memory | **Keep** — Ops Stability F1; not ticketing |
| `runtime_hygiene_service` | Git/tmp/storage report | **Keep** — ops CLI only |
| `projects.trust_level` | Decorative for automation | **Keep** — visibility until ADR-002 engine |
| Governance 17 files | High doc mass | **Keep** — canonical; sync ENFORCEMENT_MATRIX |
| `DECISIONS.md` ADR-001..007 | Historical MVP | **Archive label** — see `docs/adr/` for Stage 5 |
| ARCHITECTURE Hermes «future» | **Was paper** | **Fixed** in Consolidation — optional implemented |
| Stage 5 entities | Not built | **Governance-only** — STAGE5_CONTENT_STUDIO.md |
| Second media block in document_detail | Legacy duplicate | **Keep** collapsed in `<details>` |

### Core path (do not treat as dead)

`pipeline.py`, `publish_service.py`, `release_candidate_service.py`, `revision_service.py`, `rewrite_service.py`, worker, scheduler (idle when off).

---

## 5. Feature flags — truth table

| Flag | Production typical | Misread risk |
|------|-------------------|--------------|
| `ENABLE_AUTOMATION` + `ENABLE_SCHEDULER` | false | «Off» vs enqueue rule when on |
| `ENABLE_AUTO_PUBLISH` | false | Name implies enable; **blocks** publish when true |
| `ENABLE_PUBLISHING` | true | ≠ public publish |
| `ENABLE_HERMES` | false | Module exists anyway |
| `trust_level` in DB | 0 | ≠ automation permission |

---

## 6. What must NOT be automated yet

- Source auto-enqueue (unless explicit ops + trust engine)
- Editorial approve / RC approve
- Publish draft without RC QA discipline
- Stage 5 generation batches
- Auto-public
- Trust-based promotion without human sign-off

---

## Related

- [ROADMAP.md](ROADMAP.md) — shipped phases A–D (2026-05-20)
- [governance/ENFORCEMENT_MATRIX.md](governance/ENFORCEMENT_MATRIX.md)
- [OPERATIONS.md](OPERATIONS.md) — RC-first workflow
