# Rollback Policy — Scrap

Операционный откат без уничтожения audit trail. **Current** = mostly manual, CRMFlow24-side for drafts/public.

## Principles

| | |
|---|---|
| **Required** | Rollback **preserves** DB history (`publish_runs`, revisions, `llm_runs`) |
| **Required** | Rollback **≠** delete audit records |
| **Forbidden** | Destructive silent cleanup (purge rows without log) |
| **Forbidden** | Scrap unpublish CRMFlow24 public post **today** (P3) |
| **Current** | Draft rollback = operator in CRMFlow24 admin |
| **Target** | Auto-public rollback needs CRMFlow24 contract + ADR-003 |

## Rollback scope

| Layer | What can roll back | What cannot (Current) |
|-------|-------------------|------------------------|
| CRMFlow24 draft | Archive/delete draft (manual) | Scrap auto-delete remote |
| CRMFlow24 public | Unpublish in CRMFlow24 admin | Scrap API unpublish |
| Scrap revision | New revision supersede | In-place edit old revision |
| Scrap RC | Reject / new RC | Unapprove without audit |
| publish_run | Retry new run; mark failed | Erase failed history |
| automation | Cancel run; disable rule | Delete `automation_runs` |
| Queue | Cancel queued jobs | Lost audit if hard-delete |

## Operator recovery visibility (Current)

Diagnostics `/admin/diagnostics` (incl. replay_determinism, recovery_normalization, consistency_guarantees), `/admin/failed-items`, and `/admin/integrity` expose **read-only** recovery/integrity/predictability reports. **Supersede stale approved RC** archives the row with notes (audit preserved) — not delete. This is **operator remediation** — not automated rollback. Persistent incident rows: `operational_incidents` (bounded, not ticketing).

## Incident table

| Incident | Rollback path | Complexity | Current/Target |
|----------|---------------|------------|----------------|
| Wrong draft published | CRMFlow24 archive draft; Scrap note on RC/publication | **low** | **Current** |
| Wrong revision in draft | New revision + new RC + republish (force if needed) | **medium** | **Current** |
| Bad rewrite/SEO | Rerun → new revision; reject RC | **low** | **Current** |
| Quality false positive | Operator waive / rerun quality | **low** | **Current** |
| publish_run failed_retryable | API retry after fix | **low** | **Current** |
| publish_run wrong payload sent | Fix + new publish_run; CRMFlow24 duplicate 409 | **medium** | **Current** |
| Automation runaway | Kill switch; cancel runs; trust demotion | **medium** | **Current** |
| Hallucination in live public post | CRMFlow24 unpublish/edit; Scrap incident log | **high** | **Current** (manual public) |
| Auto-public mistake (future) | CRMFlow24 + SEO/cache + Scrap audit | **critical** | **Target** |
| Stage 5 bad batch | Cancel batch jobs; reject briefs | **medium** | **Target** |

## Action matrix

| Action | Allowed | Forbidden |
|--------|---------|-----------|
| Delete CRMFlow24 draft manually | **yes** (operator) | Scrap cron delete |
| Create new `document_revision` | **yes** | Edit old revision in-place |
| Reject release_candidate | **yes** | Delete RC row |
| `force=true` republish | **yes** with audit | Routine without reason |
| Cancel `automation_run` | **yes** | Hide run from admin |
| Purge `llm_runs` | **no** | GDPR process only with policy |
| Reset task to `queued` | **yes** (ops) | Infinite auto loop |
| Emergency `ENABLE_PUBLISHING=false` | **yes** | — |

## Draft rollback (Current)

1. Identify `publish_run` / `publication_record` / `draft_url`.
2. Operator opens CRMFlow24 admin → archive or delete draft post.
3. Scrap: `draft_review_status` / notes; reject RC if needed.
4. Fix content → new revision → new RC → republish if desired.

**Required:** do not assume Scrap removing draft remotely.

## Revision rollback

- **Cannot** roll back immutable revision — create **new** revision with corrected content.
- RC tied to old revision → **reject** or abandon; create new RC after QA.

## Publish rollback

| State | Action |
|-------|--------|
| success wrong content | CRMFlow24 draft fix + optional new publish_run |
| failed_retryable | retry API |
| failed_terminal | fix root cause; new run |
| dry_run | no external effect — no rollback needed |

**Idempotency:** republish may 409 — use `force` with documented reason.

## Automation rollback

1. `ENABLE_AUTOMATION=false`
2. Disable all rules
3. Cancel `queued` / `cancel_requested` on `running`
4. Mark stale `running` → `failed`
5. Review `logs_json`; no delete runs

**Replay-safe:** re-run rule after fix creates **new** `automation_run` id.

## Queue rollback

- Stop worker/scheduler (extreme).
- Cancel pending jobs — jobs remain in DB as cancelled/skipped.
- **Forbidden** hard-delete queue rows without audit (Target DLQ still rows).

## Emergency rollback

```text
ENABLE_PUBLISHING=false
→ ENABLE_AUTOMATION=false + ENABLE_SCHEDULER=false
→ cancel automation runs
→ freeze new RC approve (ops discipline)
→ CRMFlow24: hold drafts if incident severe
→ trust emergency downgrade to L0 (TRUST_POLICY)
→ PROJECT_LOG + operator comms
```

## Trust downgrade after incidents

| Incident | Trust action |
|----------|--------------|
| Wrong draft to production target | review; possible demotion |
| Hallucination published (public) | **L0** + kill automation |
| Automation runaway | **L0** + disable rules |
| Repeated publish failures | freeze auto-draft (Target) |

## Rollback drills (Recommended)

| Drill | Frequency |
|-------|-----------|
| Kill-switch automation | quarterly |
| Wrong draft archive in CRMFlow24 | quarterly |
| Stale `automation_run` recovery | monthly |
| Target: auto-public tabletop | before 5G |

## Logging requirements

| Field | Required |
|-------|----------|
| operator identity | admin session / API user |
| incident id | PROJECT_LOG entry |
| entity ids | document, RC, publish_run |
| reason for force | text |
| before/after revision | revision numbers |

## Operator communication

| Audience | When |
|----------|------|
| Content owner | wrong draft / public incident |
| Dev/on-call | kill switch, provider outage |
| CRMFlow24 admin | manual unpublish coordination |

**Required:** no public communication claiming rollback complete until CRMFlow24 state verified.

## Related

- [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md)
- [STATE_MACHINES.md](STATE_MACHINES.md)
- [ADR-003](../adr/ADR-003-auto-draft-vs-auto-public.md)
