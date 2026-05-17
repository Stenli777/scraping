# Деплой

## Перед изменениями

```bash
sudo cp /etc/nginx/sites-enabled/apicli.crmflow24.ru.conf /root/backup-nginx-$(date +%F)/
# при наличии scrap config — тоже backup
```

## systemd

```bash
sudo cp /opt/scrap/deploy/systemd/scrap-api.service /etc/systemd/system/
sudo cp /opt/scrap/deploy/systemd/scrap-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scrap-api scrap-worker
sudo systemctl start scrap-api scrap-worker
```

## nginx

```bash
sudo cp /opt/scrap/deploy/nginx/scrap.crmflow24.ru.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/scrap.crmflow24.ru.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## HTTPS (Let's Encrypt)

```bash
sudo certbot --nginx -d scrap.crmflow24.ru
```

Не трогать конфиги `hermes.crmflow24.ru` и `/opt/cliproxyapi`.

## Проверка

```bash
curl -s http://127.0.0.1:8800/health
curl -sI https://scrap.crmflow24.ru/health
```
