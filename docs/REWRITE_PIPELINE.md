# Rewrite pipeline

## Провайдеры

| provider | env | Статус |
|----------|-----|--------|
| `mock` | `REWRITER_PROVIDER=mock` | dev/fallback |
| `cliproxy` | `CLIPROXYAPI_*` | **production** |
| `lm_studio` | `LM_STUDIO_BASE_URL` | **deprecated** — файл есть, **не** в `registry.py` |

## Подключение CLIProxyAPI

Использовать `/opt/cliproxyapi` (не изменять без команды). В `.env`:

```
REWRITER_PROVIDER=cliproxy
CLIPROXYAPI_BASE_URL=...
CLIPROXYAPI_API_KEY=...
```

Секреты только в `.env`, chmod 600.
