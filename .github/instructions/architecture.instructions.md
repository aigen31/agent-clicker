---
description: Подробная архитектура проекта agent-clicker — структура модулей, классов, компонентов, контрактов и потоков данных. Загружается при проектировании, реализации и ревью кода любого компонента сервиса.
applyTo: '**'
---

# agent-clicker — Архитектура проекта

> Документ описывает **как именно** реализовать сервис, заданный в [technical_specification.instructions.md](./technical_specification.instructions.md). Структура классов, контракты, потоки данных, lifecycle компонентов, контейнерное окружение. Все принципы и стек из тех. спецификации действуют без изменений.

> **⚠️ Production-реальность (важно, переопределяет §3/§4/§13 при конфликте):**
> Таблица `tasks` находится во **внешней** БД, на которую сервис имеет **только `SELECT` и `UPDATE`**. Схема жёстко зафиксирована владельцем БД и **не подлежит ALTER**:
> `id INTEGER PK`, `ad_id INTEGER NOT NULL` (FK→ads), `status VARCHAR NOT NULL`, `description TEXT NOT NULL`, `link VARCHAR NOT NULL`, `created_at TIMESTAMP DEFAULT now()`, `exec_time TIMESTAMP NULL`. Никаких enum/check-ограничений на status. Прочих колонок нет.
>
> Следствия:
> 1. **Две БД.** `EXTERNAL_TASKS_DSN` (внешняя, read+update на `tasks`) и `INTERNAL_STATE_DSN` (наша, owned). В dev обе могут быть одной локальной Postgres.
> 2. **Все служебные поля** (`attempts`, `max_attempts`, `last_error`, `worker_id`, `locked_at`, `profile`, `result`) переезжают в **`internal.task_runtime(task_id PK, ...)`**.
> 3. **Status — VARCHAR.** Значения: `created` (= pending, исходный статус из прод), `in_progress`, `done`, `failed`, `skipped`, `scheduled` (резерв под backoff). Без ENUM.
> 4. **`exec_time` — `TIMESTAMP WITHOUT TIME ZONE`** (UTC по соглашению). В коде все datetime — naive UTC (`datetime.utcnow()`).
> 5. **Admin Panel:** создание/удаление задач (`POST/DELETE /api/tasks`) доступно **только в dev-режиме** (флаг `enable_task_mutations`). В прод-режиме эндпоинты возвращают 403.
> 6. **Лизинг — cross-DB best-effort.** Сначала `SELECT ... FOR UPDATE SKIP LOCKED` + `UPDATE external.tasks SET status='in_progress', exec_time=now()` в транзакции внешней БД; затем upsert в `internal.task_runtime`. При сбое второго шага — компенсирующий `UPDATE external.tasks SET status='created'`.
> 7. **Watchdog** определяет зависшие задачи по `internal.task_runtime.locked_at < now() - lease_timeout AND status='in_progress'` (через JOIN external→internal по id) и возвращает их в `created`.

---

## 0. Общие архитектурные принципы


1. **Слоистая архитектура.** Чёткое разделение:
   - **Domain** (`domain/`) — DTO, enum, value-objects. Без зависимостей от инфраструктуры.
   - **Infrastructure** (`db/`, `proxy/`, `llm/`, `observability/`) — внешние интеграции.
   - **Application** (`queue/`, `workers/`, `browser/`) — бизнес-логика воркеров.
   - **Interface** (`admin/`) — HTTP/WebSocket интерфейс.
2. **Dependency Injection через композицию.** Зависимости передаются в конструктор. Глобальных синглтонов нет, кроме `Settings`, `LogBroadcaster`, `SettingsStore`, создаваемых в composition root (`main.py`).
3. **Async-only.** Любой I/O — через `await`. CPU-bound операции (хеши, мелкая сериализация) допустимы синхронно; тяжёлые — через `asyncio.to_thread`.
4. **Graceful shutdown.** Все долгоживущие компоненты реализуют `async def start()` и `async def stop()`. Главный процесс ловит `SIGTERM/SIGINT`, останавливает приём новых задач, дожидается завершения in-flight задач до `LEASE_TIMEOUT_SECONDS`, затем отменяет.
5. **Контракты — pydantic / frozen dataclass.** Все DTO между слоями — `pydantic.BaseModel` либо `dataclass(frozen=True, slots=True)`. ORM-объекты наружу из репозитория не отдаются.
6. **Идемпотентность.** Любая операция изменения статуса задачи в репозитории — атомарна и условна (`WHERE status = ...`).
7. **Конфигурация — двухуровневая.**
   - **Static `Settings`** (env-only) — секреты, DSN, хост/порт. Иммутабельны на старте.
   - **Dynamic settings** (`AgentSettings`, `BrowserProfileDefaults`, `WorkerRuntimeSettings`) — хранятся в таблице `settings`, редактируются из Admin Panel, читаются `SettingsStore` (кеш с TTL).

---

## 1. Структура репозитория

```
agent-clicker/
├── docker/
│   ├── Dockerfile                       # multi-stage, ставит chromium через playwright
│   └── entrypoint.sh                    # ждёт postgres, прогоняет alembic, запускает app
├── docker-compose.yml                   # app + postgres
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── .env.example
├── .dockerignore
├── docs/
├── src/
│   └── agent_clicker/
│       ├── __init__.py
│       ├── __main__.py                  # python -m agent_clicker → asyncio.run(main.run())
│       ├── main.py                      # composition root
│       ├── lifecycle.py                 # Lifespan, signal handlers, graceful shutdown
│       ├── config.py                    # Settings + dynamic-settings pydantic-модели
│       │
│       ├── domain/
│       │   ├── task.py                  # TaskStatus, TaskDTO, TaskResult, TaskFilters, Page
│       │   └── profile.py               # ProxyLease, ProfileSpec
│       │
│       ├── db/
│       │   ├── engine.py                # create_async_engine, async_sessionmaker
│       │   ├── models.py                # SQLAlchemy: Task, Setting
│       │   ├── repository.py            # TaskRepository, SettingsRepository
│       │   └── migrations/
│       │       ├── env.py
│       │       └── versions/0001_initial.py
│       │
│       ├── settings_store.py            # SettingsStore: кеш + bootstrap
│       │
│       ├── llm/
│       │   └── factory.py               # build_llm(AgentSettings, Settings) → ChatOpenAI
│       │
│       ├── proxy/
│       │   └── pool.py                  # ProxyPool, ProxyLease
│       │
│       ├── profiles/
│       │   ├── catalog.py               # UA_CATALOG, VIEWPORT_PRESETS, GEO_LOCALE_TZ
│       │   └── factory.py               # ProfileFactory
│       │
│       ├── browser/
│       │   ├── runner.py                # AgentRunner, AgentRunResult
│       │   └── callbacks.py             # StepStreamCallback, DoneCallback
│       │
│       ├── queue/
│       │   ├── dispatcher.py            # Dispatcher: polling + лизинг
│       │   └── watchdog.py              # Watchdog: возврат зависших lease
│       │
│       ├── workers/
│       │   ├── worker.py                # Worker
│       │   └── pool.py                  # WorkerPool
│       │
│       ├── observability/
│       │   ├── logging.py               # configure_logging, JsonFormatter, ContextFilter
│       │   ├── broadcaster.py           # LogBroadcaster, LogBroadcastHandler
│       │   └── artifacts.py             # ArtifactStore
│       │
│       └── admin/
│           ├── app.py                   # create_app(...)
│           ├── dependencies.py          # FastAPI DI
│           ├── schemas.py               # request/response модели
│           ├── routers/
│           │   ├── tasks.py
│           │   ├── settings.py
│           │   ├── artifacts.py
│           │   ├── health.py
│           │   └── logs_ws.py
│           ├── templates/{base,tasks,settings,logs}.html
│           └── static/{app.js,style.css}
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── artifacts/                            # gitignored, mount-point в docker
```

---

## 2. Domain-слой

### 2.1 `domain/task.py`

- **`TaskStatus`** (StrEnum): `pending | scheduled | in_progress | done | failed | skipped`
- **`TaskDTO`**: полное представление задачи — id, ad_id, status, description, link, created_at, exec_time, attempts, max_attempts, last_error, worker_id, locked_at, profile (JSONB), result (JSONB)
- **`TaskResult`**: итог выполнения — is_successful, steps, duration_seconds, final_result, artifacts_dir, error, scheduled_at, started_at, finished_at
- **`TaskFilters`**: опциональные фильтры для Admin API — status, ad_id, created_from, created_to
- **`Page[T]`**: generic-пагинация — items, total, page, page_size

### 2.2 `domain/profile.py`

- **`ProxyLease`** (frozen dataclass): server, username, password, geo — учётные данные прокси; пароль **не попадает** в аудит
- **`ProfileSpec`** (frozen dataclass): user_agent, viewport_width/height, device_scale_factor, locale, timezone_id, proxy; метод `to_audit_dict()` — безопасная сериализация для записи в `tasks.profile` (без паролей)

---

## 3. Configuration (`config.py`)

### 3.1 Static `Settings` (env-only)

Поля (из env / `.env`), иммутабельны после старта:
- **DB**: `database_url`
- **LLM**: `llm_api_key` (SecretStr), `llm_base_url`
- **Proxy**: `proxy_provider_url`, `proxy_provider_token` (SecretStr), `proxy_list` (CSV строка)
- **Infra**: `artifacts_dir`, `log_level`, `log_buffer_size`
- **Admin**: `admin_host`, `admin_port`, `admin_allow_public`
- **Boot defaults** (копируются в таблицу `settings` при первом запуске): `boot_worker_concurrency`, `boot_lease_timeout_seconds`, `boot_max_attempts`, `boot_backoff_base_seconds`, `boot_min/max_time_on_site_seconds`, `boot_llm_model`, `boot_agent_*`, `boot_browser_*`

### 3.2 Dynamic settings

**`AgentSettings`**: llm_model, max_steps, use_vision, use_thinking, max_failures, step_timeout, max_actions_per_step, enable_planning, extend_system_message

**`BrowserProfileDefaults`**: headless, disable_security, wait_between_actions, minimum_wait_page_load_time, wait_for_network_idle_page_load_time, highlight_elements, enable_default_extensions, cross_origin_iframes, max_iframes

**`WorkerRuntimeSettings`**: worker_concurrency, lease_timeout_seconds, max_attempts, backoff_base_seconds, min_time_on_site_seconds, max_time_on_site_seconds

Хранение: таблица `settings(key TEXT PK, value JSONB, updated_at TIMESTAMPTZ)`. Три фиксированных ключа: `agent`, `browser`, `worker`. Первая инициализация — `SettingsStore.bootstrap()`.

---

## 4. DB-слой

### 4.1 `db/models.py`

**`Task`** (таблица `tasks`):
- Колонки: id (BigInteger PK), ad_id (BigInteger), status (SAEnum `task_status`), description (Text), link (Text), created_at (TIMESTAMPTZ, server_default=now()), exec_time (TIMESTAMPTZ), attempts (Integer), max_attempts (Integer), last_error (Text), worker_id (Text), locked_at (TIMESTAMPTZ), profile (JSONB), result (JSONB)
- Индексы: `(status, exec_time)`, частичный `(exec_time) WHERE status IN ('pending','scheduled')`

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

---

## 6. Proxy

### 6.1 `proxy/pool.py`

**`ProxyPool(settings)`**:
- `start()`: загружает список из `PROXY_LIST` (env, CSV) или HTTP-запросом к `PROXY_PROVIDER_URL`; запускает периодическое обновление
- `stop()`: останавливает фоновые задачи
- `acquire(*, preferred_geo)` → `ProxyLease | None`: round-robin/random выбор; None если пул пуст — задача исполняется напрямую (dev-режим)
- `release(lease, *, healthy)`: помечает unhealthy прокси на backoff (не выдавать N минут)

Если в env нет ни `PROXY_PROVIDER_URL`, ни `PROXY_LIST` — пул пуст, `acquire()` всегда возвращает `None`. Это валидный dev-режим.

---

## 7. Profiles

### 7.1 `profiles/catalog.py`

Статические наборы (минимум):
- `UA_CATALOG: list[UAEntry]` — ≥20 реальных User-Agent (Chrome/Firefox/Safari × Win/Mac/iOS/Android), каждый с допустимыми viewport-пресетами.
- `GEO_LOCALE_TZ: dict[str, tuple[str, str]]` — `"US" → ("en-US", "America/New_York")`, и т.д.

### 7.2 `profiles/factory.py`

**`ProfileFactory(defaults: BrowserProfileDefaults, settings: Settings)`**:
- `build_spec(*, proxy)` → `ProfileSpec`: чистая функция — случайный UA + согласованный viewport/dpr; locale/TZ из `GEO_LOCALE_TZ[proxy.geo]` если geo задан, иначе random из набора
- `build_browser_profile(spec)` → `BrowserProfile`: ProfileSpec + BrowserProfileDefaults → `browser_use.BrowserProfile` (`user_data_dir=None` для изоляции сессий, `proxy=ProxySettings(...)` или None, все timing-параметры из defaults)

`defaults` читается из `SettingsStore` перед каждой задачей в `AgentRunner`, и `ProfileFactory` пересоздаётся либо принимает свежий snapshot — см. §11.

---

## 8. LLM

### 8.1 `llm/factory.py`

`build_llm(agent: AgentSettings, static: Settings)` → `ChatOpenAI`: создаёт langchain `ChatOpenAI` с model/api_key/base_url из настроек. Смена модели — только через `AgentSettings.llm_model`. Никаких других LLM-провайдеров.

---

## 9. Browser runner

### 9.1 `browser/callbacks.py`

**`StepStreamCallback(task_id, worker_id, logger)`**: `register_new_step_callback` — на каждом шаге пишет structured-log с `extra={task_id, worker_id, step_no}`; логи автоматически попадают в `LogBroadcaster` через `LogBroadcastHandler`

**`DoneCallback(task_id, worker_id, logger)`**: `register_done_callback` — логирует итог выполнения агента

### 9.2 `browser/runner.py`

**`AgentRunResult`** (frozen dataclass): is_successful, steps, duration_seconds, final_result, artifacts_dir, history_summary, started_at, finished_at

**`AgentRunner(settings_store, artifact_store, static)`**:
- `run(*, task, worker_id, browser_profile)` → `AgentRunResult`:
  1. Читает свежие `AgentSettings` + `WorkerRuntimeSettings` из store
  2. `task_text = f"Перейди на {task.link} и выполни: {task.description}"`
  3. `extend_system_message` = композиция пользовательского текста из `AgentSettings` + шаблон с MIN/MAX_TIME_ON_SITE из `WorkerRuntimeSettings`
  4. Создаёт `browser_use.Agent(...)` со всеми параметрами, `StepStreamCallback`, `DoneCallback`, `output_dir=artifact_store.dir_for(task.id)`
  5. `hard_timeout = min(step_timeout × max_steps, lease_timeout − 30)`; `await asyncio.wait_for(agent.run(), timeout=hard_timeout)`
  6. Парсит `AgentHistoryList` → `AgentRunResult`; исключения не перехватывает — ответственность Worker

**Важно:** `runner` не пишет в БД и не управляет статусом задачи — это ответственность `Worker`.

---

## 10. Queue / Dispatcher / Watchdog

### 10.1 `queue/dispatcher.py`

**`Dispatcher(repo, settings_store, out_queue, worker_id_prefix, poll_interval_seconds=1.0)`**:
- `start()` / `stop()`: запуск/остановка фоновой задачи `_loop()`
- `_loop()`: читает `WorkerRuntimeSettings`; `free = queue.maxsize − queue.qsize()`; лизингует `batch_size=free` задач через `repo.lease_batch`; кладёт в очередь; sleep=0 если был batch, иначе poll_interval

### 10.2 `queue/watchdog.py`

**`Watchdog(repo, settings_store, interval_seconds=30.0)`**:
- `start()` / `stop()`: запуск/остановка фоновой задачи
- Каждые `interval_seconds` вызывает `repo.reclaim_expired(lease_timeout)` и логирует количество восстановленных задач

---

## 11. Workers

### 11.1 `workers/worker.py`

Один экземпляр = одна корутина, обрабатывает задачи последовательно.

**`Worker(worker_id, in_queue, repo, settings_store, proxy_pool, profile_factory_builder, runner)`**:

`run()`: event loop — `await in_queue.get()` → устанавливает contextvars (`current_task_id`, `current_worker_id`) → `await _handle(task)` → `in_queue.task_done()` + сброс context

`_handle(task)`:
1. `browser_defaults = await settings_store.get_browser()` → `profile_factory = profile_factory_builder(browser_defaults)` (пересоздание перед каждой задачей — свежие настройки браузера)
2. `proxy = await proxy_pool.acquire(preferred_geo=None)`
3. `spec = profile_factory.build_spec(proxy=proxy)` → `browser_profile` → `profile_audit = spec.to_audit_dict()`
4. `run_result = await runner.run(task=task, worker_id=..., browser_profile=...)`
5. Успех → `repo.mark_done(...)` + `proxy_pool.release(healthy=True)`
6. `is_successful=False` → `_retry_or_fail(...)` + `proxy_pool.release(healthy=True)`
7. `CancelledError` → `repo.mark_failed(retry_at=now())` + `raise` (graceful shutdown)
8. `Exception` → `_retry_or_fail(...)` + `proxy_pool.release(healthy=False)`; не пробрасывает наружу

`_retry_or_fail(task, profile_audit, error)`: если `attempts < max_attempts` → exponential backoff `delay = backoff_base × 2^(attempts−1)` → `repo.mark_failed(retry_at=now()+delay)`, иначе → `repo.mark_failed(retry_at=None)` → status=failed

### 11.2 `workers/pool.py`

**`WorkerPool(settings_store, build_worker, worker_id_prefix)`**:
- `start()`: читает `worker_concurrency` из store (фиксируется на старте), создаёт N `Worker`, запускает `asyncio.create_task(w.run())` для каждого
- `stop()`: дожидается опустошения queue (таймаут `lease_timeout_seconds`), затем отменяет оставшиеся таски

> Изменение `worker_concurrency` из Admin Panel применяется только после рестарта процесса. В UI поле помечается «requires restart».

---

## 12. Observability

### 12.1 `observability/logging.py`

- `current_task_id: ContextVar[int | None]`, `current_worker_id: ContextVar[str | None]` — контекст для логов.
- `ContextFilter` — добавляет `record.task_id` и `record.worker_id` из contextvars.
- `JsonFormatter` — формирует JSON: `{ts, level, logger, task_id, worker_id, msg, ...extra}`.
- `configure_logging(level, broadcaster)`:
  - корневой `StreamHandler` (stdout) + `LogBroadcastHandler(broadcaster)`;
  - переопределяет логгеры `browser_use`, `playwright`, `httpx` (suppress INFO для httpx);
  - выключает `uvicorn.access` шумные логи в одной строке формата.

### 12.2 `observability/broadcaster.py`

**`LogBroadcaster(buffer_size=2000)`**: in-memory pub/sub + кольцевой буфер последних N записей:
- `publish_nowait(record: dict)`: вызывается из `logging.Handler` (sync); кладёт в буфер, рассылает по подписчикам non-blocking
- `snapshot()` → `list[dict]`: текущий буфер (для отправки при подключении WebSocket)
- `subscribe()` → `AsyncIterator[dict]`: async generator с пер-подписчиковым `asyncio.Queue(maxsize=1000)`; при overflow дропает старейшие + warning

**`LogBroadcastHandler`**: `logging.Handler` — передаёт каждую запись в `broadcaster.publish_nowait(record_as_dict)`

### 12.3 `observability/artifacts.py`

**`ArtifactFile`** (pydantic BaseModel): name, size, modified_at

**`ArtifactStore(root: Path)`**:
- `dir_for(task_id)` → `Path`: создаёт `{root}/{task_id}/`; передаётся в `Agent(output_dir=...)`
- `list_for(task_id)` → `list[ArtifactFile]`
- `resolve_safe(task_id, filename)` → `Path`: валидация regex имени файла, проверка path traversal
- `cleanup_older_than(days)` → `int`: удаляет старые артефакты, возвращает count

---

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

---

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

## 15. Flow одной задачи

```mermaid
sequenceDiagram
    autonumber
    participant Ext as External
    participant DB as Postgres(tasks)
    participant D as Dispatcher
    participant Q as asyncio.Queue
    participant W as Worker
    participant PP as ProxyPool
    participant PF as ProfileFactory
    participant R as AgentRunner
    participant BU as browser_use.Agent
    participant LB as LogBroadcaster
    participant WS as Admin /ws/logs

    Ext->>DB: INSERT pending
    loop poll
      D->>DB: lease_batch (SELECT FOR UPDATE SKIP LOCKED + UPDATE in_progress RETURNING)
      D-->>Q: put TaskDTO
    end
    W->>Q: get TaskDTO
    W->>PP: acquire(geo)
    PP-->>W: ProxyLease | None
    W->>PF: build_spec + build_browser_profile
    W->>R: run(task, profile)
    R->>BU: Agent(...).run() (asyncio.wait_for hard timeout)
    BU-->>LB: step callbacks (structured logs)
    LB-->>WS: stream
    BU-->>R: AgentHistoryList
    R-->>W: AgentRunResult
    alt success
      W->>DB: mark_done(result, profile)
      W->>PP: release(healthy=True)
    else failure / exception
      W->>DB: mark_failed(error, profile, retry_at?)
      W->>PP: release(healthy=False)
    end
```

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

---

## 17. Best practices & failure modes (обязательны в коде)

1. **Сессии БД** — короткоживущие: `async with session_factory() as s: async with s.begin(): ...`.
2. **Лизинг и блокировки** — одна транзакция `WITH ... FOR UPDATE SKIP LOCKED + UPDATE RETURNING`. Никаких race conditions.
3. **Hard timeout на `agent.run()`** — `asyncio.wait_for(timeout=lease_timeout - 30)`. Защита от превышения lease.
4. **Cleanup tmpdir** — `browser-use` сам управляет tmpdir при `user_data_dir=None`. В `finally` явно вызвать `await agent.close()` если API его предоставляет.
5. **PII / секреты в логах** — `last_error` обрезается до 4000 символов; в логи не пишутся `description`, прокси-пароли, LLM-ключи.
6. **Backpressure WebSocket** — bounded `asyncio.Queue(maxsize=1000)` per subscriber; overflow → drop oldest + warning.
7. **`updated_at`** — отображается во фронте Admin, чтобы операторы видели применение настроек.
8. **Health endpoints** — `/healthz`, `/readyz` для docker `healthcheck`.
9. **Метрики** — точка расширения `observability/metrics.py` оставлена пустой (заглушка), Prometheus подключается позже.
10. **Тесты**:
    - `tests/conftest.py` поднимает Postgres через `testcontainers-python` (либо использует `pytest-postgresql`).
    - `browser_use.Agent` мокается `AsyncMock`, возвращающим stub `AgentHistoryList`.
    - Каждый репозиторный метод покрыт хотя бы одним тестом (happy + один failure).

---

## 18. Уточнения / доработки бизнес-логики поверх тех. спецификации

1. **Таблица `settings`** добавлена. Без отдельного хранилища невозможно «изменять настройки без перезапуска».
2. **`SettingsStore` с TTL=5s** — компромисс между свежестью и нагрузкой; явно вызываемая `invalidate()` после `update_*` сводит lag к нулю в active-replica деплое.
3. **Обновление `exec_time` в `lease_batch`** атомарно с переходом в `in_progress`.
4. **`result.scheduled_at` / `result.started_at` / `result.finished_at`** заполняются в `Worker._handle`.
5. **Hard timeout** на `agent.run()` обязателен.
6. **WebSocket back-pressure** — обязательная защита от медленных клиентов.
7. **Health endpoints** добавлены — нужны для docker `healthcheck`.
8. **`worker_concurrency` — фиксируется на старте.** Динамическое масштабирование out-of-scope MVP; в Admin UI поле помечено «requires restart».
9. **ProxyPool допускает пустой пул** — задачи идут напрямую (dev-режим).
10. **`extend_system_message`** — композиция: пользовательский текст из `AgentSettings.extend_system_message` + динамический блок с `MIN/MAX_TIME_ON_SITE_SECONDS` из `WorkerRuntimeSettings`.
11. **CancelledError при graceful shutdown** освобождает lease (`retry_at=now()`) — задача мгновенно подхватится после рестарта, без ожидания watchdog.
12. **Lease-таймаут > hard-таймаут agent.run** на 30s — окно для записи `mark_failed/mark_done` до того, как watchdog заберёт задачу.
13. **`ProfileFactory` пересоздаётся в воркере** перед каждой задачей со свежими `BrowserProfileDefaults` из `SettingsStore` — это гарантирует применение настроек браузера без рестарта.

---

## 19. Чеклист для реализации нового модуля

При добавлении кода (AI и человеком одинаково):

- [ ] Все публичные функции/методы имеют type-hints, `mypy --strict` проходит.
- [ ] I/O — только async; никаких `requests`, `time.sleep`, синхронных DB-вызовов.
- [ ] Конфигурация — через `Settings` / `SettingsStore`, не через `os.environ`.
- [ ] БД-операции — только через `TaskRepository` / `SettingsRepository`.
- [ ] Логирование — `logger.info("event.name", extra={...})`, без секретов и PII.
- [ ] Исключения в горячем пути воркера ловятся, задача не валит процесс.
- [ ] Есть unit-тест happy-path и хотя бы один failure-path.
- [ ] Если меняется схема БД — есть alembic-миграция.
- [ ] Если добавлен новый dynamic-параметр — обновлены `AgentSettings` / `BrowserProfileDefaults` / `WorkerRuntimeSettings`, дефолты в `bootstrap()`, поле в Admin UI и роутере.
- [ ] Если код запускает внешний процесс или сетевой вызов — есть таймаут.
- [ ] Никаких прямых вызовов Playwright API — только через `browser_use.Agent`.
