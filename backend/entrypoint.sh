#!/bin/sh

set -e

if [ "${RUN_DB_INIT:-false}" = "true" ]; then
  echo "[entrypoint] Ensuring database schema exists..."
  python init_db.py
fi

exec "$@"
