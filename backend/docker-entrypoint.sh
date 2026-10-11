#!/bin/sh
# Roles:
#   api      the FastAPI server (uvicorn, WEB_CONCURRENCY processes)
#   worker   the RabbitMQ notification worker (python -m app.worker)
#   migrate  one-shot: alembic upgrade head, then idempotent bootstrap
#            (default tenant, system roles, first admin, notification templates)
set -eu

wait_for_db() {
  python - <<'PY'
import sys, time
from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.database_url)
for attempt in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        sys.exit(0)
    except Exception as exc:
        print(f"waiting for database ({exc.__class__.__name__})...", flush=True)
        time.sleep(1)
print("database never became reachable", file=sys.stderr)
sys.exit(1)
PY
}

case "${1:-api}" in
  api)
    exec uvicorn app.main:app \
      --host 0.0.0.0 --port "${PORT:-8000}" \
      --workers "${WEB_CONCURRENCY:-2}" \
      --timeout-keep-alive "${KEEPALIVE_SECONDS:-75}" \
      --no-server-header
    ;;
  worker)
    wait_for_db
    exec python -m app.worker
    ;;
  migrate)
    wait_for_db
    alembic upgrade head
    python -m app.core.bootstrap
    ;;
  *)
    exec "$@"
    ;;
esac
