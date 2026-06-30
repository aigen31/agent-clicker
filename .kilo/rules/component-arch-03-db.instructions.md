---
description: 'agent-clicker — Архитектура: DB-слой (models, repository, migrations) и SettingsStore. Загружать при работе с db/ или settings_store.py.'
applyTo: '**/db/**'
---
# agent-clicker — Архитектура проекта

## 4. DB-слой

### 4.1 `db/models.py`

**`Task`** (таблица `tasks`):
- Колонки: id (BigInteger PK), ad_id (BigInteger), status (SAEnum `task_status`), description (Text), link (Text), created_at (TIMESTAMPTZ, server_default=now()), exec_time (TIMESTAMPTZ), attempts (Integer), max_attempts (Integer), last_error (Text), worker_id (Text), locked_at (TIMESTAMPTZ), profile (JSONB), result (JSONB)
- Индексы: `(status, exec_time)`, частичный `(exec_time) WHERE status IN ('pending','scheduled')`

**`TaskRuntime`** (таблица `task_runtime`, internal): служебные поля задачи — task_id (BigInteger PK), attempts, max_attempts, last_error, worker_id, locked_at, profile (JSONB, аудит-профиль браузера), result (JSONB, результат агента), cookies (JSONB), updated_at

**`TaskProxy`** (таблица `task_proxies`): прокси-конфигурация, привязанная к конкретному task_id — task_id (BigInteger PK), proxy_host, proxy_port, proxy_login, proxy_password, created_at, updated_at.
  *Эта таблица может быть в внешней БД с правами на создание таблицы, если пользователь имеет соответствующие разрешения.*

**`AdProxyConfig`** (таблица `ad_proxy_configs`): прокси-конфигурация, привязанная к ad_id — id (Integer PK), ad_id (unique), proxy_host, proxy_port, proxy_login, proxy_password, created_at, updated_at.
  *Эта таблица может быть в внешней БД с правами на создание таблицы, если пользователь имеет соответствующие разрешения.*

**`Setting`** (таблица `settings`): key (Text PK), value (JSONB), updated_at (TIMESTAMPTZ, auto-update)

### 4.2 `db/repository.py`

**TaskRepository** — единственная точка доступа к `tasks`. Возвращает только `TaskDTO`.

- `lease_batch(*, worker_id, batch_size, lease_timeout)` → `list[TaskDTO]`: атомарный лизинг — CTE `SELECT ... FOR UPDATE SKIP LOCKED` + `UPDATE SET status='in_progress', worker_id, locked_at=now(), attempts+1, exec_time=now() RETURNING *`
- `mark_done(task_id, *, result, profile)`: `WHERE status='in_progress'` → done, очищает locked_at
- `mark_failed(task_id, *, error, profile, retry_at)`: если retry_at → status=pending + exec_time=retry_at + сброс locked_at/worker_id; иначе → status=failed
- `mark_skipped(task_id, *, reason)`
- `reclaim_expired(*, lease_timeout)` → `int`: watchdog — `WHERE status='in_progress' AND locked_at < now() - interval` → pending; возвращает количество восстановленных
- `list_tasks(*, filters, page, page_size)` → `Page[TaskDTO]`
- `get_task(task_id)` → `TaskDTO | None`
- `create_task(*, ad_id, link, description, exec_time, max_attempts)` → `TaskDTO`
- `delete_task(task_id)` → `bool`
- `requeue(task_id)` → `TaskDTO`: только из failed/done/skipped → status=pending, attempts=0, last_error=NULL, exec_time=NULL, locked_at=NULL

**SettingsRepository** — CRUD по таблице `settings`:
- `get(key)` → `dict | None`
- `upsert(key, value)` → `None`
- `get_all()` → `dict[str, dict]`

**AdProxyRepository** — CRUD по таблице `ad_proxy_configs`:
- `get_by_ad_id(ad_id)` → `AdProxyConfigDTO | None`
- `list_all()` → `list[AdProxyConfigDTO]`
- `upsert(ad_id, proxy_host, proxy_port, ...)` → `AdProxyConfigDTO`
- `delete(ad_id)` → `bool`

**TaskProxyRepository** — CRUD по таблице `task_proxies`:
- `get_by_task_id(task_id)` → `TaskProxyConfigDTO | None`
- `list_all()` → `list[TaskProxyConfigDTO]`
- `upsert(task_id, proxy_host, proxy_port, ...)` → `TaskProxyConfigDTO`
- `delete(task_id)` → `bool`

### 4.3 Миграция `0001_initial.py`

Создаёт ENUM `task_status`, таблицы `tasks` и `settings` со всеми индексами (включая частичный). Дальнейшие изменения схемы — **только** через новые alembic-миграции.

---

## 5. `SettingsStore`

Кеширующая обёртка над `SettingsRepository` с TTL **5 секунд** (минимизирует БД-нагрузку; изменения из Admin Panel применяются практически сразу).

**`SettingsStore(repo, ttl_seconds=5.0)`**:
- `bootstrap(*, defaults)`: идемпотентная инициализация — вставляет отсутствующие ключи из defaults, мерджит новые поля в существующие (forward-совместимость)
- `get_agent()` / `get_browser()` / `get_worker()`: возвращают типизированные настройки с TTL-кешем 5 секунд
- `update_agent(new)` / `update_browser(new)` / `update_worker(new)`: upsert в БД + автоматически `invalidate()`
- `invalidate()`: принудительный сброс кеша; вызывается автоматически после каждого `update_*`

Singleton-инстанс создаётся в `main.py` и пробрасывается во все компоненты.
