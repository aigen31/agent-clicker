#!/usr/bin/env bash
set -euo pipefail
echo "[entrypoint] waiting for postgres..."
python - <<'PY'
import os, asyncio, asyncpg
async def wait():
    dsn = os.environ['INTERNAL_STATE_DSN'].replace('+asyncpg', '')
    for _ in range(60):
        try:
            c = await asyncpg.connect(dsn); await c.close(); return
        except Exception:
            await asyncio.sleep(1)
    raise SystemExit('postgres not ready')
asyncio.run(wait())
PY
echo "[entrypoint] running migrations..."
alembic upgrade head
echo "[entrypoint] exec: $@"
exec "$@"
