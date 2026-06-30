---
description: 'agent-clicker — Архитектура: Dispatcher, Watchdog, Worker, WorkerPool. Загружать при работе с queue/ или workers/.'
applyTo: '**/queue/**'
---
# agent-clicker — Архитектура проекта

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
