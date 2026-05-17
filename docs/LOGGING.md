# Logging

## Locations

| Source | Path / command |
|--------|----------------|
| Application file logs | `storage/logs/` (LOG_DIR) |
| API service | `journalctl -u scrap-api -f` |
| Worker service | `journalctl -u scrap-worker -f` |
| Uvicorn access | journald (scrap-api unit) |

## Configuration

- `LOG_LEVEL` in `.env` (default `INFO`)
- `LOG_DIR=storage/logs` — created at startup

## Recommended rotation

- Use **journald** retention for systemd units (`SystemMaxUse=` in journald.conf)
- For `storage/logs/`: logrotate weekly, keep 4–8 copies, compress

Example logrotate snippet (not installed automatically):

```text
/opt/scrap/storage/logs/*.log {
  weekly
  rotate 8
  compress
  missingok
  notifempty
}
```

## Troubleshooting

```bash
# Last API errors
journalctl -u scrap-api -p err -n 50 --no-pager

# Worker task failures
journalctl -u scrap-worker | grep -i error | tail -30

# Config warnings at startup
journalctl -u scrap-api | grep -i "Config:" | tail -20
```
