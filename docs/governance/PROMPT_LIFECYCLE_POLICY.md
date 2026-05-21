# Prompt Lifecycle Policy — Scrap

Управление версиями промптов и overrides. **Current:** `prompt_templates`, `prompt_versions`, `project_prompt_overrides`, `prompt_service` + code fallback (`app/llm/prompts.py`). **Target:** experiment framework, stricter gates.

## Principles

| | |
|---|---|
| **Required** | No **silent** replacement of active prompt |
| **Required** | Active version identified in `llm_runs` as `key:version` |
| **Required** | Deprecated prompts not auto-reactivated |
| **Forbidden** | Edit active `prompt_versions` row in-place (content change = new version) |
| **Forbidden** | Experimental prompt on production project without flag |

## Prompt roles (mapping to AI_POLICY)

| Role | Prompt keys (examples) |
|------|------------------------|
| rewriter | `rewrite_article_v1` |
| reviewer | review templates |
| seo | SEO enrich |
| quality | quality review JSON |
| topic_cleanup | `topic_cleanup_v1` |
| Target: brief_generator | TBD |
| Target: outline_planner | TBD |
| Target: article_writer | TBD |
| Target: media | image prompt templates |

## Lifecycle states

```text
draft → in_review → active → deprecated → archived
         ↘ rejected
experimental (isolated) → promote to in_review OR discard
```

| Prompt status | Meaning |
|---------------|---------|
| `draft` | Editable; not used in production |
| `in_review` | Candidate; needs operator/owner approve |
| `active` | Used by `prompt_service` for key |
| `deprecated` | No new runs; old llm_runs still reference |
| `archived` | Hidden from picker; retained for audit |
| `experimental` | Only pilot projects / `content_pilots` |

## Change type table

| Change type | Requires review? | Notes |
|-------------|------------------|-------|
| New version (new row) | **yes** | Default path |
| Typo fix on draft | no | Before activate |
| Activate version | **yes** | Two-person rule (Target) for production |
| Project override | **yes** | Visible in admin |
| Deprecate active | **yes** | Must activate another version first |
| Rollback to prior version | **yes** | Reactivate old version row — not edit |
| Emergency revert | **yes** + PROJECT_LOG | Incident-driven |

## Versioning

| | |
|---|---|
| **Current** | `prompt_versions.version` monotonic per template key |
| **Required** | Immutable version body once `active` |
| **Required** | `llm_runs.prompt_template` = `{key}:{version}` |

## Project overrides

| | |
|---|---|
| **Current** | `project_prompt_overrides` in DB |
| **Required** | Override visible in admin + auditable |
| **Forbidden** | Override without project_id scope |
| **Required** | Fallback chain: override → DB active → code fallback |

## Compatibility

| Change | Compatibility rule |
|--------|-------------------|
| JSON output schema change | New key or major version; QA smoke |
| Model alias change | Document in DECISIONS; monitor llm_runs errors |
| Stricter prompt | May increase `needs_revision` — expected |

## Prompt audit

| Event | Record |
|-------|--------|
| activate | `pipeline_event` or admin audit (Target) |
| each LLM call | `llm_runs` + prompt key:version |
| override set/clear | operator id + timestamp (Target) |

## Dangerous prompts

| Pattern | Risk |
|---------|------|
| «Ignore previous rules» | injection / policy bypass |
| Unbounded output length | cost |
| Publish/auto-approve instructions | A3 violation |
| Crawl/enqueue instructions | M3 violation |

| | |
|---|---|
| **Forbidden** | Prompts that instruct model to bypass editorial/publish gates |
| **Required** | Review checklist for new active prompts |

## Rollback prompts

1. Identify last known good `prompt_versions.id`.
2. Set current active → `deprecated`.
3. Activate prior version (reactivate, not content edit).
4. Monitor `llm_runs` error rate 24h.
5. PROJECT_LOG entry.

**Required:** rollback does not delete bad version rows (audit).

## Experimental prompts

| | |
|---|---|
| **Target** | Flag `is_experimental=true`; only pilot project IDs |
| **Forbidden** | Experimental on `crmflow24-production-v2` path |
| **Required** | Isolated evaluation before promote |

## Migration strategy

| Phase | Action |
|-------|--------|
| Code-only prompts | Import to `prompt_templates` as v1 |
| Split keys per role | Avoid one mega-prompt |
| Stage 5 keys | New templates before writer automation |

## Future testing framework (Target)

| Capability | Purpose |
|------------|---------|
| Fixture documents | regression on rewrite output shape |
| Golden sample compare | score drift detection |
| Shadow mode | run new prompt, don't persist |

## Prompt quality evaluation

| Metric | Use |
|--------|-----|
| quality verdict rate | prompt change review |
| llm_run error % | provider vs prompt |
| operator rerun rate | dissatisfaction signal |

## Hallucination incident response

1. Deprecate suspect prompt version (stop new runs).
2. Rollback per procedure above.
3. Rerun affected documents → new revisions.
4. TRUST_POLICY demotion if cluster.
5. Root cause in PROJECT_LOG (prompt vs model vs source).

## Related

- [AI_POLICY.md](AI_POLICY.md)
- [PROVENANCE_MODEL.md](PROVENANCE_MODEL.md)
- [ENFORCEMENT_MATRIX.md](ENFORCEMENT_MATRIX.md)
