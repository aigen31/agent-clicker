---
description: 'agent-clicker — Архитектура: composition root (main.py, lifecycle) и контейнерное окружение (Dockerfile, docker-compose). Загружать при работе с main.py, lifecycle, docker/.'
applyTo: '**/main.py'
---
# agent-clicker — Архитектура проекта

## 14. Composition root (`main.py`)

Порядок инициализации (`async def run()`):
1. `Settings()` — загрузка статической конфигурации из env
2. `LogBroadcaster(buffer_size=settings.log_buffer_size)` + `configure_logging(level, broadcaster)` — единый поток логов
3. `create_async_engine(database_url, pool_pre_ping=True)` + `async_sessionmaker(expire_on_commit=False)`
4. `SettingsRepository(session_factory)` → `SettingsStore(repo)` → `await bootstrap(defaults)` из `Settings.boot_*` значений
5. `TaskRepository`, `ProxyPool(settings)`, `ArtifactStore(Path(settings.artifacts_dir))`, `AgentRunner(settings_store, artifact_store, settings)`
6. `asyncio.Queue(maxsize=worker_concurrency)` + `Dispatcher(task_repo, settings_store, queue, ...)` + `Watchdog(task_repo, settings_store)` + `WorkerPool(settings_store, build_worker, ...)`
7. `_validate_admin_binding(settings)` → `create_app(...)` → `uvicorn.Server(uvicorn.Config(...))`
8. `async with Lifespan([proxy_pool, dispatcher, watchdog, worker_pool]):` → `await admin_server.serve()` (блокирует до SIGTERM/SIGINT)

`build_factory(defaults)` и `build_worker(wid)` — замыкания (передаются в `WorkerPool`).
- `__aenter__`: `await c.start()` для каждого компонента **в порядке** списка.
- `__aexit__`: `await c.stop()` **в обратном порядке** с общим таймаутом = `lease_timeout_seconds + 30`.
- Регистрирует обработчики `SIGTERM`/`SIGINT` → ставят `admin_server.should_exit = True`.

---

## 16. Контейнерное окружение

### 16.1 `docker/Dockerfile` (multi-stage)

```dockerfile
# --- builder ---
FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# --- runtime ---
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
      libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libxcomposite1 \
      libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
      libdrm2 fonts-liberation tini ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY alembic.ini ./
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && python -m playwright install --with-deps chromium \
 && mkdir -p /app/artifacts \
 && useradd -m -u 1000 app \
 && chown -R app:app /app /ms-playwright
USER app
ENV ARTIFACTS_DIR=/app/artifacts ADMIN_HOST=0.0.0.0 ADMIN_PORT=8080
EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD ["python", "-m", "agent_clicker"]
```

### 16.2 `docker/entrypoint.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "[entrypoint] waiting for postgres..."
python - <<'PY'
import os, asyncio, asyncpg
async def wait():
    dsn = os.environ['DATABASE_URL'].replace('+asyncpg', '')
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
```

### 16.3 `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: agent
      POSTGRES_DB: agent_clicker
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent -d agent_clicker"]
      interval: 5s
      timeout: 3s
      retries: 20

  app:
    build:
      context: .
      dockerfile: docker/Dockerfile
    depends_on:
      postgres:
        condition: service_healthy
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://agent:agent@postgres:5432/agent_clicker
      ADMIN_HOST: 0.0.0.0
    ports:
      - "127.0.0.1:8080:8080"   # admin доступен только с хоста
    volumes:
      - ./artifacts:/app/artifacts
    shm_size: "1gb"             # критично для Chromium
    init: true
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8080/healthz"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s

volumes:
  pgdata: {}
```

### 16.4 `.dockerignore`

```
.git
.venv
__pycache__
*.pyc
artifacts/
.env
tests/
docs/
```
