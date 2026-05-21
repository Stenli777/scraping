# Enforcement Matrix — Scrap

Связь policy/invariant → runtime enforcement. Обновлять при изменении кода или governance.

**Legend — enforcement status:**

| Status | Meaning |
|--------|---------|
| **fully enforced** | Code/API blocks or guarantees |
| **partially enforced** | Some paths guarded; bypass/ops possible |
| **governance-only** | Documented; not reliably enforced in code |
| **planned** | Target; not implemented |

**Severity:** critical | high | medium | low

---

## SYSTEM_INVARIANTS

| ID | Policy / invariant | Enforcement | Location | Severity | Gap |
|----|-------------------|-------------|----------|----------|-----|
| C1 | Revision immutable | **fully enforced** | `document_revisions` append-only | critical | — |
| C2 | Raw not silent overwrite on rerun | **partially enforced** | pipeline rerun paths | high | No DB constraint on raw_html |
| C3 | RC binds one revision | **partially enforced** | RC create + QA `revision_current` + approve/publish block | critical | RC DB auto-invalidate on create still Target |
| C4 | Revision change → new RC | **partially enforced** | stale guards + auto-archive open RC on new revision + supersede-stale admin | critical | Historical approved+stale until operator supersede or new RC |
| C5 | Generated provenance | **planned** | Stage 5 | high | Not built |
| C6 | No fake scrape URL | **governance-only** | payload builder | critical | No validator for generated (Target) |
| P1 | publish_run → revision_id | **fully enforced** | publish_service | critical | — |
| P2 | publication_record ≠ public | **governance-only** | ops/docs | high | Misinterpretation risk |
| P3 | No Scrap public publish | **fully enforced** | no public API | critical | — |
| P4 | RC → QA → approve → publish | **partially enforced** | readiness + stale on approve/publish + admin disabled buttons | high | Legacy document publish still exists (deprecated `<details>`) |
| P5 | ENABLE_PUBLISHING semantics | **partially enforced** | env gate | medium | Naming confusion |
| P6 | No auto-public | **fully enforced** | `ENABLE_AUTO_PUBLISH=false` | critical | Future flag not added |
| A1 | CLIProxyAPI only | **partially enforced** | cliproxy rewriter | critical | Hermes/optional paths need audit |
| A2 | Hermes optional | **fully enforced** | `ENABLE_HERMES=false` default | high | — |
| A3 | AI not decision owner | **partially enforced** | manual editorial/publish | critical | `force=true` bypass |
| A4 | llm_runs audit | **partially enforced** | LLM stages | high | Gaps if stage skips logging |
| A5 | Explicit model alias | **partially enforced** | rewriter config | high | Missing alias → fail paths vary |
| A6 | No bypass rejected without force | **partially enforced** | publish gating + `force_reason` | critical | force still bypasses gates when reason given |
| M1 | Kill switch automation | **fully enforced** | env + disable rules + cancel | critical | Operator must know procedure |
| M2 | AUTO_PUBLISH off | **fully enforced** | env default | critical | — |
| M3 | No infinite gen loops | **fully enforced** | no Stage 5 batch | high | Future queue caps planned |
| M4 | No auto enqueue discovery | **partially enforced** | automation off default; `enqueue` rule if automation on | high | Misread when ENABLE_AUTOMATION=true |
| M5 | trust never auto-up | **partially enforced** | `projects.trust_level` column | high | No promotion workflow / rule engine yet |
| M6 | Auto-draft L2+ gates | **planned** | Target | critical | — |
| U1 | pipeline_events | **partially enforced** | pipeline | medium | Not all admin actions |
| U2 | automation_runs | **partially enforced** | scheduler | medium | — |
| U3 | publish_runs audit | **fully enforced** | DB | critical | — |
| U4 | No secrets in logs | **partially enforced** | logging policy | critical | Operator discipline |
| H1 | Human overrides AI | **partially enforced** | workflow | high | Automation Target risk |
| H2 | No silent overwrite edits | **partially enforced** | `operator_touched` + automation skip | high | Full UI indicator planned |
| H3 | Force audit | **partially enforced** | `force_used` + `force_reason` | high | Legacy runs pre-Phase-A lack reason |
| H4 | Rerun → new revision | **fully enforced** | revision service | high | — |

---

## TRUST_POLICY

| Policy | Enforcement | Location | Severity | Gap |
|--------|-------------|----------|----------|-----|
| Level 0–1 effective today | **partially enforced** | `projects.trust_level` default 0; **visibility-only** | high | Rule `min_trust` not wired; column ≠ permission |
| Human-only promotion | **governance-only** | TRUST_POLICY | high | No promotion workflow |
| Auto demotion triggers | **governance-only** | — | medium | No metrics job |
| Emergency L0 downgrade | **partially enforced** | manual ops | critical | No one-click demotion |
| Level 3 not production | **fully enforced** | not implemented | critical | — |
| min_trust on automation rules | **planned** | rule metadata | high | — |

---

## AUTOMATION_POLICY

| Policy | Enforcement | Location | Severity | Gap |
|--------|-------------|----------|----------|-----|
| ENABLE_SCHEDULER/AUTOMATION false | **fully enforced** | env production default | critical | — |
| Per-rule limits | **partially enforced** | scheduler engine | high | Misconfigured rules possible |
| No auto editorial/publish | **partially enforced** | rule types / ops | critical | Wrong rule definition risk |
| Gates before auto-draft | **planned** | Target | critical | — |
| Kill switch procedure | **partially enforced** | env + admin + governance smoke | critical | — |
| Batch caps Stage 5 | **planned** | — | critical | — |

---

## PUBLISH_POLICY

| Policy | Enforcement | Location | Severity | Gap |
|--------|-------------|----------|----------|-----|
| Draft only to CRMFlow24 | **fully enforced** | WebhookPublisher | critical | — |
| Preferred RC path | **partially enforced** | readiness checks | high | Direct document publish API |
| Quality gate | **partially enforced** | `ENABLE_QUALITY_REVIEW` | high | force bypass |
| Editorial gate | **partially enforced** | `ENABLE_EDITORIAL_WORKFLOW` | high | force bypass |
| Mock target isolation | **partially enforced** | target config | medium | Operator error risk |
| article_v2 source.type generated | **planned** | payload | high | — |

---

## HUMAN_OVERRIDE_POLICY

| Policy | Enforcement | Location | Severity | Gap |
|--------|-------------|----------|----------|-----|
| Operator priority | **partially enforced** | manual workflows | high | — |
| Force requires audit | **partially enforced** | `force_used` + `force_reason` | high | Legacy runs may lack reason |
| rejected blocks publish | **partially enforced** | gating | critical | force path |
| UI shows manual vs AI edit | **planned** | admin | low | — |

---

## Highest-risk gaps

| Rank | Gap | Severity | Why |
|------|-----|----------|-----|
| 1 | C6 / generated fake source_url (Target) | critical | Trust/provenance break |
| 2 | P2 publication_record semantics | high | Ops mistake = «already live» |
| 3 | trust promotion / rule engine | high | Column only; ADR-002 not accepted |
| 4 | RC DB auto-invalidate on revision change | high | Stale blocked at approve/publish; not auto-invalidated at create |
| 5 | Legacy document publish path | medium | Deprecated; RC-first ops discipline |
| 6 | Full operator vs AI edit UI | low | `operator_touched` exists; indicator planned |

---

## Recommended enforcement order

1. **Generated payload validator** — when Stage 5 starts (source.type, no fake URL).
2. **trust_level rule engine** — ADR-002 accept + `min_trust` on automation rules.
3. **RC auto-invalidate** — DB status when revision changes (Target).
4. **Governance drift check** — quarterly review ENFORCEMENT_MATRIX vs code.
5. ~~Stale publish guard~~ — **done** Phase A (`validate_revision_current_for_publish`).
6. ~~Force reason~~ — **done** Phase A (`force_reason` column + validation).
7. ~~Invariant smoke~~ — **done** `check_governance_invariants.py` in `run_all.py`.
7b. ~~Stale RC approve gap~~ — **done** Runtime Safety Phase (`approve_release_candidate` + admin UI).
7c. ~~Force/legacy operator visibility~~ — **done** Runtime Safety Phase (`force_confirm`, publish_runs highlight, legacy collapsed).
7d. ~~Authority boundary catalog in diagnostics~~ — **done** Cohesion Phase G (`runtime_authority_service`, admin authority panel).
8. ~~Diagnostics safety/bounds~~ — **done** Phase C (`runtime_diagnostics_service`, localhost API guard, incident triage).
9. ~~Operational history/trends~~ — **done** Phase D (`operational_snapshots`, bounded retention, not metrics platform).
10. ~~Replay/retry operator ambiguity~~ — **done** Predictability Phase J (`runtime_predictability_service`, verdict catalog, normalized retry chain visibility).

---

## Runtime vs governance drift risks

| Risk | Symptom | Mitigation |
|------|---------|------------|
| Docs say RC-only; ops use document publish | Skipped QA | OPERATOR_RUNBOOK + lint in release checklist |
| ARCHITECTURE lists extra pipeline states vs SCRAPING_PIPELINE | Confusion | STATE_MACHINES.md as canonical ops view |
| ENABLE_PUBLISHING=true read as public | Incident | Rename/docs; admin banner |
| Automation enabled without trust | Runaway drafts | TRUST_POLICY + ADR-002 |
| Hermes path bypasses cliproxy audit | A1 gap | Audit all LLM entrypoints |

---

## Consolidation reference

Truth-alignment inventory (force semantics, dead code, legacy paths): [CONSOLIDATION_INVENTORY.md](../CONSOLIDATION_INVENTORY.md).

## Related

- [SYSTEM_INVARIANTS.md](SYSTEM_INVARIANTS.md)
- [STATE_MACHINES.md](STATE_MACHINES.md)
- [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md)
