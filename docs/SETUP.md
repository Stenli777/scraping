# Установка

## Требования

- Ubuntu 22.04+, Python 3.10+
- PostgreSQL 14+
- nginx (reverse proxy)

## Шаги

```bash
sudo mkdir -p /opt/scrap
cd /opt/scrap
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

### PostgreSQL

```bash
sudo -u postgres psql -c "CREATE USER scrap WITH PASSWORD 'scrap';"
sudo -u postgres psql -c "CREATE DATABASE scrap OWNER scrap;"
```

В `.env`:

```
DATABASE_URL=postgresql+psycopg2://scrap:SCRAP_PASSWORD@127.0.0.1:5432/scrap
```

```bash
alembic upgrade head
```

### Запуск

```bash
./scripts/run_api.sh
./scripts/run_worker.sh
```

## Тестовые URL

См. `docs/SCRAPING_PIPELINE.md`.
