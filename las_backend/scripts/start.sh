#!/usr/bin/env sh
set -eu

echo "[startup] Running alembic migrations"
alembic upgrade head

echo "[startup] Starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
