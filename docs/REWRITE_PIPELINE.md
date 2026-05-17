# Rewrite pipeline

## Провайдеры

| provider | env | Статус |
|----------|-----|--------|
| `mock` | `REWRITER_PROVIDER=mock` | по умолчанию |
| `cliproxy` | `CLIPROXYAPI_*` | интерфейс готов |
| `lm_studio` | `LM_STUDIO_BASE_URL` | интерфейс готов |

## Подключение CLIProxyAPI

Использовать `/opt/cliproxyapi` (не изменять без команды). В `.env`:

```
REWRITER_PROVIDER=cliproxy
CLIPROXYAPI_BASE_URL=...
CLIPROXYAPI_API_KEY=...
```

Секреты только в `.env`, chmod 600.
