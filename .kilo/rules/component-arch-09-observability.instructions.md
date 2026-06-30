---
description: 'agent-clicker — Архитектура: логирование, LogBroadcaster, ArtifactStore. Загружать при работе с observability/.'
applyTo: '**/observability/**'
---
# agent-clicker — Архитектура проекта

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
