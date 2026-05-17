# Деплой

## HTTPS

Сертификат Let's Encrypt для `scrap.crmflow24.ru`:

- Путь: `/etc/letsencrypt/live/scrap.crmflow24.ru/`
- Срок: до **2026-08-15** (автообновление certbot)
- Команда: `certbot --nginx -d scrap.crmflow24.ru --non-interactive --agree-tos --redirect`

Backup nginx перед certbot: `/root/backup-nginx-2026-05-17-0934/scrap.crmflow24.ru.conf`

## systemd

```bash
sudo systemctl restart scrap-api scrap-worker
sudo systemctl status scrap-api scrap-worker
```

## nginx

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Не трогать `hermes.crmflow24.ru.conf`, `apicli.crmflow24.ru.conf`.

## Проверка

```bash
curl -s https://scrap.crmflow24.ru/health
curl -s https://scrap.crmflow24.ru/admin
```

## Обновление кода

```bash
cd /opt/scrap
# git pull или scp
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
systemctl restart scrap-api scrap-worker
```
