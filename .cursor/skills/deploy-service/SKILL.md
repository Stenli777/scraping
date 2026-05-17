# deploy-service

## Цель

Задеплоить или обновить Scrap на сервере.

## Шаги

1. Backup nginx: `cp /etc/nginx/sites-enabled/*.conf /root/backup-nginx-$(date +%F)/`
2. `cd /opt/scrap && git pull` (или rsync).
3. `source .venv/bin/activate && pip install -r requirements.txt`
4. `alembic upgrade head`
5. `systemctl restart scrap-api scrap-worker`
6. `nginx -t && systemctl reload nginx`
7. `curl /health`
8. `docs/PROJECT_LOG.md`, `docs/DEPLOYMENT.md` при изменении процесса.

## Проверки

- `/health` ok
- worker active
- не затронуты hermes/cliproxyapi сервисы

## Лог

версия commit, systemd status, curl результат.
