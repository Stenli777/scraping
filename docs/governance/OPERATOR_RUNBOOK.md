# Operator Runbook — Scrap (governance)

Production workflow для оператора. Дополняет [OPERATIONS.md](../OPERATIONS.md), [RELEASE_RUNBOOK.md](../RELEASE_RUNBOOK.md), [admin-operator-workflow.md](../admin-operator-workflow.md). **Current** paths only unless marked **Target**.

## Роли

| | |
|---|---|
| **Current** | Operator использует Admin UI `/admin` и API docs `/docs`. |
| **Required** | Production publish — trained operator; не anonymous API. |

## Ежедневный workflow (Current)

1. Dashboard / **Диагностика** (`/admin/diagnostics`) — incident triage, trends из **bounded snapshots** (история накапливается при открытии страницы, throttle 15 мин); затем failed tasks.
2. Discovery queue — manual enqueue only; не enqueue `quality_blocked`.
3. Document pipeline — review → rewrite → SEO → **manual** quality.
4. Editorial queue — approve/reject.
5. Release candidates — QA → approve → publish draft (**approve/publish disabled in admin if revision stale**).
6. При инцидентах — `/admin/diagnostics` (operational_predictability, consistency_guarantees, replay_determinism, recovery_normalization) → `/admin/integrity` при stale approved RC.
7. Перед retry publish — колонка **Replay verdict** на `/admin/publish-runs` или блок replay_determinism в diagnostics; следовать `operator_action` из catalog (`runtime_predictability_service`); `blocked_*` / `manual_retry_allowed=false` → новый RC, не blind retry.
6. Draft reviews — feedback после CRMFlow24 check.
7. LLM runs / automation runs — spot-check errors.

## Проверка quality

| Step | Action |
|------|--------|
| 1 | Open document detail → quality block / score |
| 2 | If missing: `Run quality` (admin or `POST .../run-quality`) |
| 3 | Verdict `approved` / `needs_revision` / `rejected` |
| 4 | **rejected** → do not publish; fix or abandon |
| 5 | **needs_revision** → rerun rewrite/SEO or manual edit; new revision |

**Required:** do not publish with `ENABLE_QUALITY_REVIEW=true` and verdict below threshold unless documented `force`.

## Проверка Release Candidate

| Check | Pass criteria |
|-------|----------------|
| QA score | ≥ project threshold (default base 70 + bonuses − penalties) |
| Revision | RC `document_revision_id` = latest intended revision |
| Canonical / duplicate warnings | Understand; critical → do not approve |
| Editorial | `approved_for_publish` if workflow enabled |
| Target / payload | `crmflow24-production-v2` / `article_v2` |
| Smoke/test flags | Blocked for production publish |

Actions: `Run QA` → review blocking issues → **Approve** or **Reject** → publish draft.

Admin: `/admin/release-candidates/{id}`.

## Publish draft (Current)

**Preferred path:**

```text
RC approved → Publish draft (select target, avoid unnecessary force)
→ verify publish_run success → publication_record → draft_url
```

| | |
|---|---|
| **Required** | `ENABLE_PUBLISHING=true` |
| **Forbidden** | Routine use of raw `/api/publish` or document-level publish as primary path |
| **Required** | Dry-run first on new targets or after payload change |

Post-publish: open `draft_url` in CRMFlow24 admin; record `draft_review_feedback` in Scrap.

## Rollback (Current)

Scrap **does not** delete CRMFlow24 drafts automatically.

| Situation | Action |
|-----------|--------|
| Wrong draft sent | Archive/delete draft in **CRMFlow24 admin**; mark RC/publication failed in Scrap notes |
| Wrong revision published | Do not republish without new RC; fix content → new revision → new RC |
| RC approve/publish fails «revision stale» | Rerun rewrite → **create new RC**; или `/admin/integrity` → **Supersede** (archives stale approved, audit kept) |
| Duplicate publish blocked (409) | Expected; use `force` only with reason **and** admin `force_confirm` if intentional republish |

**Target:** formal `ROLLBACK_POLICY.md` — not in scope iteration 2.

## Остановить automation (kill switch)

| Order | Action |
|-------|--------|
| 1 | Set `ENABLE_AUTOMATION=false` and/or `ENABLE_SCHEDULER=false` in `.env` |
| 2 | `systemctl restart scrap-scheduler` (if disabled) or stop unit |
| 3 | Admin → Automation → **disable** each rule |
| 4 | Cancel queued runs: `POST /api/automation/runs/{id}/cancel` |
| 5 | Mark stale running: `mark-failed` if needed |
| 6 | Document in PROJECT_LOG if production incident |

**Required:** verify `/admin/automation-runs` — no stuck `running`.

## Suspicious AI output

| Signal | Action |
|--------|--------|
| Fabricated quotes/stats | Reject quality; flag incident; consider trust demotion |
| Wrong language/tone | Rerun with project profile; new revision |
| SEO keyword stuffing | Reject; adjust prompts (prompt admin) |
| Nonsense slug/title | Fix SEO rerun |

Check linked **`llm_run`** — prompt version, model, raw error. Do not publish until operator satisfied.

## Hallucinations

1. Stop publish for affected document/RC.
2. Set quality `rejected`; editorial reject if needed.
3. Log incident (PROJECT_LOG); **Target:** trust demotion trigger.
4. Rerun rewrite/article with corrected brief (Stage 5) or manual edit.
5. New revision + new RC before any republish.

## Failed publish

| Status | Action |
|--------|--------|
| `failed_terminal` (401, 400 validation) | Fix token/payload; do not blind retry |
| `failed_retryable` | `POST /api/publish-runs/{id}/retry` after fixing upstream |
| Timeout | Check CRMFlow24 health; retry with backoff |

Verify: `GET /api/publish-targets/health`.

## Emergency procedures

| Scenario | Procedure |
|----------|-----------|
| Runaway LLM cost | Kill automation + disable cliproxy-heavy rules; pause worker if needed |
| Mass bad drafts | Stop publish; disable `ENABLE_PUBLISHING`; CRMFlow24 bulk archive |
| Suspected credential leak | Rotate `CRMFLOW24_PUBLISH_TOKEN`; never log token |
| Invariant breach | See [SYSTEM_INVARIANTS.md](SYSTEM_INVARIANTS.md) — L0 emergency |

---

## Checklists

### Daily checklist

- [ ] Failed/stale scraping tasks reviewed
- [ ] No unexpected `running` automation runs > timeout
- [ ] LLM error rate normal (`/admin/llm-runs`)
- [ ] Editorial queue not backlog-critical
- [ ] No unpublished RC with approved status > 7 days (ops hygiene)

### Pre-publish checklist

- [ ] Correct `document_revision_id` on RC
- [ ] QA passed; warnings understood
- [ ] Quality + editorial gates satisfied
- [ ] Not smoke/test document
- [ ] Target = production v2 (not mock) for real publish
- [ ] Dry-run OK if first time / after change
- [ ] Title/slug reviewed for cannibalization warnings

### Emergency checklist

- [ ] `ENABLE_AUTOMATION=false`, `ENABLE_SCHEDULER=false`
- [ ] All automation rules disabled
- [ ] Queued runs cancelled
- [ ] `ENABLE_PUBLISHING=false` if publish incident
- [ ] Incident logged PROJECT_LOG + notify owner
- [ ] Trust emergency downgrade considered ([TRUST_POLICY.md](TRUST_POLICY.md))

### Automation kill-switch (short)

```text
ENV off → restart scheduler → disable rules → cancel runs → verify admin
```

## Target (Stage 5)

When Content Studio exists: brief approve → outline review → article review before RC. See [STAGE5_CONTENT_STUDIO.md](STAGE5_CONTENT_STUDIO.md).

## Open questions

- Single on-call rotation doc vs OPERATIONS.md merge.
- CRMFlow24 bulk draft API (out of scope Scrap).
