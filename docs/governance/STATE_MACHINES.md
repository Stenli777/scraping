# State Machines — Scrap

Явные lifecycle сущностей. **Current** = фактические статусы в worker/API/docs. **Target** = Stage 5 / automation scale. Enforcement: см. [ENFORCEMENT_MATRIX.md](ENFORCEMENT_MATRIX.md).

## 1. scraping_task lifecycle

**Enforcement:** partially enforced (worker transitions).

### States (Current — primary path)

```text
queued → fetching → parsing → cleaning → [reviewing] → rewriting
      → [seo_enriching] → saving → done
```

| State | Meaning |
|-------|---------|
| `queued` | В очереди worker |
| `fetching` … `saving` | Активная стадия pipeline |
| `done` | **Terminal** — успех |
| `error` | **Terminal** — fetch/parse fatal |
| `failed_retryable` | **Terminal** для task row; rewrite/LLM fail, artifacts kept |

Optional stages: `reviewing`, `seo_enriching` — feature flags.

### Allowed transitions

| From | To | Actor |
|------|-----|-------|
| `queued` | `fetching` | worker |
| stage N | stage N+1 | worker on success |
| any active | `error` | worker on fatal fetch/parse |
| rewrite fail | `failed_retryable` | worker |
| `saving` | `done` | worker |

### Forbidden transitions

| Transition | Why |
|------------|-----|
| `done` → `fetching` without new task | Must create new `scraping_task` or explicit rerun API |
| `error` → `done` without re-queue | Invalid skip |
| skip `cleaning` with parsed body | Pipeline integrity |

### Retry

| | |
|---|---|
| **Current** | Operator: re-queue task / new scrape from discovered URL; stale reset in ops |
| **Required** | `failed_retryable` does **not** auto-retry infinitely — manual or capped automation |
| **Forbidden** | Worker loop: `failed_retryable` → `queued` without backoff/limit |

### Operator actions

- Skip / stale reset (ops); view `task_logs`, `pipeline_events`
- Manual `run-review`, `run-seo`, `rerun-rewrite` on **document** (not always new task)

### Automation actions

| | |
|---|---|
| **Current** | **Forbidden** — no auto enqueue from discovery |
| **Target** | Bounded enqueue per TRUST_POLICY + QUEUE policy |

### Rollback

- No «undo» of `done` task; new task if re-scrape needed.
- Preserves `raw_html` / logs on failure states.

### Stale / concurrency

- Worker single-poller: one task progression per poll batch.
- **Invalid:** two workers advancing same task without idempotent stage guards — **risk** (partially mitigated by DB status checks).

### Idempotency

- Re-entering same stage should not duplicate `parsed_document` rows (hash/url dedup).

---

## 2. document lifecycle (parsed_document)

**Enforcement:** partially enforced.

Logical states (composite — not always single DB enum):

```text
parsed → cleaned → [reviewed] → rewritten → [seo_enriched]
      → [quality_scored] → [editorial_gated] → RC_eligible → published_draft
```

| Phase | Indicator |
|-------|-----------|
| Parsed | `clean_text` present |
| Rewritten | `rewritten_text` |
| Quality | `content_quality_scores` verdict |
| Editorial | `editorial_status`, `approved_for_publish` |
| Published draft | `publication_record` / publish_run success |

### Forbidden

| | |
|---|---|
| **Forbidden** | Publish with empty `rewritten_text` + required SEO (Current readiness) |
| **Forbidden** | Treat document as public live without CRMFlow24 step |

### Revision coupling

```text
rerun rewrite/SEO/quality → NEW document_revision (immutable)
```

**Required:** revision change **invalidates** prior RC for publish (must new RC + QA) — [SYSTEM_INVARIANTS](SYSTEM_INVARIANTS.md) C4.

### Operator / automation

| Actor | Actions |
|-------|---------|
| Operator | rerun stages, manual edit fields, editorial approve |
| Automation | **Current:** enrichment jobs optional; **Forbidden** auto publish |

---

## 3. editorial lifecycle

**Enforcement:** partially enforced when `ENABLE_EDITORIAL_WORKFLOW=true`.

```text
[pending] → in_review → approved_for_publish | rejected | needs_revision
```

| Status (typical) | Publish |
|------------------|---------|
| not approved | **Blocked** |
| `approved` / `ready_to_publish` + `approved_for_publish=true` | Allowed (with other gates) |
| `rejected` | **Forbidden** unless `force` + audit |

### Forbidden transitions

| | |
|---|---|
| **Forbidden** | Automation sets `approved_for_publish` without operator (Current) |
| **Forbidden** | Publish while `rejected` without force |

### Rollback

- Operator reverses approval → block subsequent publish until re-approved.
- Does not delete revisions.

---

## 4. release_candidate lifecycle

**Enforcement:** partially enforced (QA service + admin).

```text
draft → qa_pending → qa_passed | qa_failed
     → pending_approval → approved | rejected
     → publish_pending → publish_succeeded | publish_failed
     → [draft_reviewed] → [public_confirmed Target audit]
```

(Exact enum labels may vary in DB — treat as logical states.)

### Allowed transitions

| From | To | Actor |
|------|-----|-------|
| create | `draft` | operator/API |
| draft | QA run | operator `run-qa` |
| QA pass | `pending_approval` | system |
| approve | `approved` | operator |
| approved | publish_draft | operator (Current) / automation (Target L2) |
| publish ok | linked `publish_run` success | publish_service |

### Forbidden

| | |
|---|---|
| **Forbidden** | Publish RC bound to **superseded** `document_revision_id` without re-QA |
| **Forbidden** | Auto-approve RC at trust < 2 (Target policy) |

### Retry

- QA re-run after content fix.
- New RC after revision change — **Required**.

### Rollback

- Reject RC → no publish on that candidate.
- Does not delete revision history — [ROLLBACK_POLICY.md](ROLLBACK_POLICY.md).

---

## 5. publish_run lifecycle

**Enforcement:** fully enforced for status recording.

```text
pending → running → success | failed_retryable | failed_terminal
         [dry_run path → success without publication_record]
```

| Terminal | Meaning |
|----------|---------|
| `success` (not dry) | Draft ACK; may create `publication_record` |
| `failed_retryable` | Network/5xx — manual retry API |
| `failed_terminal` | 401, 400 validation — fix config |

### Forbidden

| | |
|---|---|
| **Forbidden** | Infinite auto-retry without `retry_count` cap |
| **Forbidden** | `success` interpreted as **public live** (P2) |

### Idempotency

- Duplicate publish → 409 unless `force=true` (CRMFlow24 idempotency contract).

### Operator

- Retry `failed_retryable`; never blind retry `failed_terminal`
- `force` → `force_used` audit

### Rollback

- Scrap does not unpublish CRMFlow24 — manual in CRMFlow24 admin.

---

## 6. automation_run lifecycle

**Enforcement:** partially enforced (`ENABLE_AUTOMATION` / scheduler).

```text
queued → running → completed | failed | skipped
              ↘ cancel_requested → cancelled
```

Stale: `running` + heartbeat timeout → `failed` (scheduler recovery / mark-failed).

| | |
|---|---|
| **Current** | Default automation **off** |
| **Forbidden** | `completed` → `queued` immediate loop without rule cooldown |

### Operator

- cancel queued; cancel_requested running; mark-failed stale

### Rollback

- Cancel does not delete run row — audit preserved.

---

## 7. Stage 5 topic lifecycle (Target)

**Not in production.** Logical machine:

```text
batch_draft → topics_imported → topic_selected
           → brief_draft → brief_approved
           → outline_pending → outline_approved
           → article_generating → article_ready
           → [seo] → [quality] → RC path (same as scraped)
```

### Required ordering

```text
brief_approved REQUIRED before outline_pending
outline_approved REQUIRED before article_generating
```

| Forbidden | |
|-----------|--|
| `article_generating` without `brief_approved` | invariant F1 |
| Autonomous `topic_selected` → enqueue scrape loop | M3 |

### Rollback (Target)

- Reject brief → block outline/article jobs.
- Deprecate batch → cancel queued generation jobs (kill switch).

---

## Cross-cutting

### Invalid transition examples

1. Publish RC#3 while document revision moved to #4 — **block**.
2. `automation_run` `running` 24h — stale recovery required.
3. Stage 5 article job without brief — **reject enqueue** (Target).

### Stale state handling

| Entity | Recovery |
|--------|----------|
| automation_run `running` | heartbeat timeout → failed; operator mark-failed |
| enrichment job `running` | same pattern (ARCHITECTURE 4H) |
| scraping_task stuck | ops stale reset |

### Concurrency

- Worker: scraping batch before enrichment (isolated).
- Scheduler: lock `scheduler_state` — single scheduler process.
- **Risk:** parallel publish attempts — mitigated by idempotency/409.

### Idempotency notes

- Stage transitions should be conditional updates on current status.
- Publish and revision snapshots are point-in-time.
