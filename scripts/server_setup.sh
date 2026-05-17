#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if ! command -v psql >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq postgresql postgresql-contrib python3-venv python3-dev libpq-dev build-essential
fi

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='scrap'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER scrap WITH PASSWORD 'scrap_prod_change_me';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='scrap'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE scrap OWNER scrap;"

cd /opt/scrap
python3 -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i 's|postgresql+psycopg2://scrap:scrap@|postgresql+psycopg2://scrap:scrap_prod_change_me@|' .env
  chmod 600 .env
fi

alembic upgrade head
echo "SETUP_OK"
