---
description: 'agent-clicker — Архитектура: AgentRunner, callbacks. Загружать при работе с browser/.'
applyTo: '**/browser/**'
---
# agent-clicker — Архитектура проекта

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
