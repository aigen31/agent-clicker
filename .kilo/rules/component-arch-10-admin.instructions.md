---
description: 'agent-clicker — Архитектура: Admin Panel (app, routers, frontend, security). Загружать при работе с admin/.'
applyTo: '**/admin/**'
---
# agent-clicker — Архитектура проекта

## 13. Admin Panel

### 13.1 `admin/app.py`

`create_app(*, repo, settings_store, broadcaster, artifact_store, static_settings)` → `FastAPI`:
- Создаёт `FastAPI(title="agent-clicker admin")`, записывает зависимости в `app.state`
- Подключает роутеры: `health_router`, `tasks_router` (`/api/tasks`), `settings_router` (`/api/settings`), `artifacts_router` (`/api/tasks`), `logs_ws_router`
- Монтирует `StaticFiles`; Jinja2-маршруты: `GET /` → tasks.html, `/settings`, `/logs`

### 13.2 Routers (контракты)

**`/api/tasks`**
- `GET /api/tasks?status=&ad_id=&from=&to=&page=1&page_size=50` → `Page[TaskDTO]`.
- `GET /api/tasks/{id}` → `TaskDTO`.
- `POST /api/tasks` body `CreateTaskRequest{ad_id, link, description, exec_time?, max_attempts?}` → `TaskDTO` (201).
- `POST /api/tasks/{id}/retry` → `TaskDTO` (только из failed/done/skipped).
- `DELETE /api/tasks/{id}` → 204.

**`/api/settings`**
- `GET /api/settings/agent` → `AgentSettings`.
- `PUT /api/settings/agent` body `AgentSettings` (full replace) → `AgentSettings`.
- Аналогично для `/browser` и `/worker`.

**`/api/tasks/{id}/artifacts`**
- `GET` → `list[ArtifactFile]`.
- `GET /api/tasks/{id}/artifacts/{filename}` → `FileResponse`. Имя валидируется regex, путь проверяется через `ArtifactStore.resolve_safe`.

**`/healthz`** → 200 если БД доступна и `WorkerPool` живёт. **`/readyz`** → 200 после bootstrap.

**`/ws/logs`**
- Опц. query: `?level=INFO&task_id=&worker_id=`.
- On connect → шлёт `broadcaster.snapshot()` (отфильтрованный), затем стримит новые записи.
- При slow consumer (заполнение очереди подписчика) — сервер закрывает соединение с code 1011.

### 13.3 Frontend

Минимальный SPA: vanilla JS + Alpine.js (CDN), 3 страницы — Tasks / Settings / Logs. Без сборки. Без auth — слушает только `127.0.0.1`.

### 13.4 Безопасность Admin

- `main.py` проверяет: если `admin_host != "127.0.0.1"` и `admin_allow_public=False` → fatal error.
- Все query/path параметры валидируются pydantic.
- CORS отключён.
- В docker app биндит `0.0.0.0:8080`, но `docker-compose.yml` пробрасывает порт как `"127.0.0.1:8080:8080"` — наружу не выставлен.
