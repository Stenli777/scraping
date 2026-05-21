# Scrap — content scraping pipeline

Manual-first production pipeline: scrape, parse, rewrite (CLIProxy), editorial/RC, draft publish to CRMFlow24. **Not** a fully autonomous content platform (automation/Stage 5 off by default).

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

См. каталог [`docs/`](docs/) и индекс [`docs/README.md`](docs/README.md).

**Roadmap:** [`docs/ROADMAP.md`](docs/ROADMAP.md) — canonical execution map (phases, tracks, next tasks).

**Governance:** [`docs/governance/`](docs/governance/) — политики; см. [`docs/CONSOLIDATION_INVENTORY.md`](docs/CONSOLIDATION_INVENTORY.md) для честной карты enforcement vs decorative.
