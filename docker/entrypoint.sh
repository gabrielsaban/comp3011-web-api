#!/usr/bin/env sh
set -eu

VENV_BIN="/app/.venv/bin"

if [ ! -x "$VENV_BIN/uvicorn" ] || [ ! -x "$VENV_BIN/alembic" ]; then
  echo "Missing expected virtualenv binaries under $VENV_BIN"
  exit 1
fi

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running Alembic migrations..."
  "$VENV_BIN/alembic" upgrade head
fi

echo "Starting API..."
exec "$VENV_BIN/uvicorn" app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-1}" \
  --log-level "${UVICORN_LOG_LEVEL:-info}"
