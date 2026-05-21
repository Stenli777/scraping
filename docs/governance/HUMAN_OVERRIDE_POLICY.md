# Human Override Policy — Scrap

Приоритет решений человека (оператора) над рекомендациями AI и автоматизацией.

## Принцип

| | |
|---|---|
| **Required** | Human/operator decision **имеет приоритет** над AI output и scheduler. |
| **Forbidden** | Ночной automation, перезаписывающий ручные правки без audit. |
| **Forbidden** | AI как final authority для publish, editorial, strategy block removal. |

## Ручные правки контента

| | |
|---|---|
| **Required** | Ручное изменение `rewritten_text`, SEO, editorial notes не должно **тихо** затираться следующим worker pass без rerun policy. |
| **Current** | Rerun rewrite/SEO из admin создаёт **новую** `document_revision`; старая сохраняется. |
| **Current** | `parsed_documents.operator_touched` (+ `_at`, `_by`) при editorial transition и rerun rewrite; automation `pipeline_progression` пропускает touched docs. |
| **Target** | UI indicator: «последний rewrite — AI» vs «поля изменены оператором». |

Если оператор отклонил AI-версию — следующий auto-run **Forbidden** без explicit rerun command.

## Rerun и revisions

| Действие | Поведение |
|----------|-----------|
| Rerun rewrite | Новый `llm_run`, новая revision, `pipeline_event` |
| Rerun SEO | То же |
| Rerun quality | Новый score/verdict; не mutate old revision in-place |
| Publish после rerun | Новый RC или re-QA (revision change → new candidate) |

**Required:** история revisions доступна в admin (`/admin/documents/{id}/revisions`).

## Состояния quality и editorial

| Verdict / status | Automation |
|------------------|------------|
| `rejected` | **Forbidden** auto publish; **Forbidden** scheduler bypass |
| `needs_revision` | **Forbidden** auto publish до исправления или operator waive |
| `approved` (quality) | Не заменяет editorial approve при `ENABLE_EDITORIAL_WORKFLOW` |

### Force bypass

| | |
|---|---|
| **Allowed** | Только с `force=true` (или admin equivalent) где API поддерживает. |
| **Current** | `publish_runs.force_used` + **`force_reason`** обязателен при `force=true` (API/admin); пустой reason → 400. |
| **Required** | operator identity в logs/admin (Target). |
| **Forbidden** | Force по умолчанию в automation rules. |

**`force_reason` — audit, not safety.** При `force=true` код **отключает** проверки ниже; stale revision и пустой контент **не** обходятся.

| Gate | Bypassed by `force=true`? |
|------|---------------------------|
| Duplicate publish | **Yes** |
| Review take / score | **Yes** — **dangerous** |
| Quality verdict / score | **Yes** — **dangerous** |
| Editorial / `approved_for_publish` | **Yes** — **dangerous** |
| Stale `document_revision` | **No** |
| Missing `rewritten_text` / SEO slug | **No** |
| `ENABLE_AUTO_PUBLISH=true` block | **No** |

См. [CONSOLIDATION_INVENTORY.md](../CONSOLIDATION_INVENTORY.md) §2.

## Release candidate и publish

| | |
|---|---|
| **Required** | Operator approve RC перед production publish-draft. |
| **Forbidden** | Auto-approve RC без trust policy Level ≥ 2 и gates (AUTOMATION_POLICY). |
| **Required** | Reject RC — блокирует publish до нового QA/кандидата. |

## Draft review (CRMFlow24)

После publish draft оператор проверяет в CRMFlow24 admin и вносит feedback в Scrap (`draft_review_*`).

| | |
|---|---|
| **Forbidden** | Scrap меняет статус поста в CRMFlow24. |
| **Required** | Feedback в Scrap — источник правды для **внутреннего** editorial follow-up, не для CRMFlow24 DB. |

## Automation cancel

Оператор может:

- `POST /api/automation/runs/{id}/cancel`;
- disable rule;
- `ENABLE_AUTOMATION=false` (kill switch).

**Required:** cancel не удаляет audit записи run.

## AI recommendations

Рекомендации (risks, QA warnings, cannibalization) — **информационные**. Применение — только оператор или явная automation policy с gates.

## Открытые вопросы

- Обязательное поле `override_reason` в admin forms.
- RBAC: кто может `force` publish на production target.
- Diff UI: revision A vs B для operator review.
