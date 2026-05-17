# Scrap — content scraping pipeline

Production-ready сервис для парсинга, очистки, рерайта и экспорта контента.

- **Путь на сервере:** `/opt/scrap`
- **Домен:** `https://scrap.crmflow24.ru`
- **Не смешивать** с `/hermes` и `/opt/cliproxyapi`

## Стек

- FastAPI + Jinja2 admin UI
- PostgreSQL + SQLAlchemy + Alembic
- Scrapling (fetch) + trafilatura/BS4 (parse)
- DB-polling worker (расширяемо до Redis/Celery/ARQ)
- JSON/Markdown backups в `storage/backups/`

## Быстрый старт (сервер)

```bash
cd /opt/scrap
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактировать DATABASE_URL и секреты
alembic upgrade head
./scripts/run_api.sh      # API + admin
./scripts/run_worker.sh   # обработка очереди
```

## Проверка

- Health: `GET /health`
- Admin: `/admin`
- API docs: `/docs`

## Документация

См. каталог [`docs/`](docs/).
