---
description: 'agent-clicker — Архитектура: domain-слой (DTO, enums, value-objects). Загружать при работе с domain/ или определением контрактов.'
applyTo: '**/domain/**'
---
# agent-clicker — Архитектура проекта

## 2. Domain-слой

### 2.1 `domain/task.py`

- **`TaskStatus`** (StrEnum): `pending | scheduled | in_progress | done | failed | skipped`
- **`TaskDTO`**: полное представление задачи — id, ad_id, status, description, link, created_at, exec_time, attempts, max_attempts, last_error, worker_id, locked_at, profile (JSONB), result (JSONB)
- **`TaskResult`**: итог выполнения — is_successful, steps, duration_seconds, final_result, artifacts_dir, error, scheduled_at, started_at, finished_at
- **`AdProxyConfigDTO`**: прокси-конфигурация, привязанная к ad_id — ad_id, proxy_host, proxy_port, proxy_login, proxy_password
- **`TaskProxyConfigDTO`**: прокси-конфигурация, привязанная к конкретному task_id — task_id, proxy_host, proxy_port, proxy_login, proxy_password
- **`TaskFilters`**: опциональные фильтры для Admin API — status, ad_id, created_from, created_to
- **`Page[T]`**: generic-пагинация — items, total, page, page_size

### 2.2 `domain/profile.py`

- **`ProxyLease`** (frozen dataclass): server, username, password, geo — учётные данные прокси; пароль **не попадает** в аудит
- **`ProfileSpec`** (frozen dataclass): user_agent, viewport_width/height, device_scale_factor, locale, timezone_id, proxy; метод `to_audit_dict()` — безопасная сериализация для записи в `tasks.profile` (без паролей)
