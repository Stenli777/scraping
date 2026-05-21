# governance-alignment

## Цель

Проверить изменение на соответствие governance **до** runtime-кода.

## Когда использовать

- automation, publish, trust, Stage 5, orchestration
- новые policy или ops-процедуры
- любой «опасный» PR

## Workflow

1. **Canonical docs** — `docs/CANONICAL_OWNERSHIP.md`, нужный `docs/governance/*.md`
2. **Invariants** — `docs/governance/SYSTEM_INVARIANTS.md`
3. **Enforcement** — `docs/governance/ENFORCEMENT_MATRIX.md` (gaps?)
4. **Roadmap phase** — `docs/ROADMAP.md` (A/B/C/D/E)
5. **Rollback** — `docs/governance/ROLLBACK_POLICY.md`
6. Только потом — код (отдельная задача, flags default off)

## Checks

- [ ] Invariants C/P/A/M/H не нарушены
- [ ] Нет hidden automation
- [ ] Audit сохранён (`llm_runs`, revisions, publish_runs)
- [ ] Нет duplicate truths в docs (ссылки, не копипаст)
- [ ] ADR не в `proposed` как основание для schema
- [ ] PROJECT_LOG запланирован

## Выход

Краткий verdict: aligned / gaps / blocked + список canonical files для обновления.
