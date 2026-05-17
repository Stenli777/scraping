# add-rewriter-provider

## Цель

Подключить новый LLM rewrite provider.

## Шаги

1. Класс в `app/rewriters/`, наследник `BaseRewriter`.
2. Регистрация в `app/rewriters/registry.py`.
3. Переменные в `.env.example` (без значений).
4. Документировать в `docs/REWRITE_PIPELINE.md`.
5. Тест с `REWRITER_PROVIDER=...` на staging.
6. `PROJECT_LOG.md`.

## Проверки

- Pipeline stage `rewriting` → `done`
- Секреты не в логах
- Fallback при недоступности API

## Лог

provider name, env vars (имена only).
