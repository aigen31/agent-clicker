---
description: 'agent-clicker — Архитектура: ProxyPool, приоритет резолвинга прокси. Загружать при работе с proxy/ или резолвингом прокси.'
applyTo: '**/proxy/**'
---
# agent-clicker — Архитектура проекта

## 6. Proxy

### 6.1 `proxy/pool.py`

**`ProxyPool(settings)`**:
- `start()`: загружает список из `PROXY_LIST` (env, CSV) или HTTP-запросом к `PROXY_PROVIDER_URL`; запускает периодическое обновление
- `stop()`: останавливает фоновые задачи
- `acquire(*, preferred_geo)` → `ProxyLease | None`: round-robin/random выбор; None если пул пуст — задача исполняется напрямую (dev-режим)
- `release(lease, *, healthy)`: помечает unhealthy прокси на backoff (не выдавать N минут)

Если в env нет ни `PROXY_PROVIDER_URL`, ни `PROXY_LIST` — пул пуст, `acquire()` всегда возвращает `None`. Это валидный dev-режим.

### 6.2 Приоритет резолвинга прокси (Worker._handle)

При выполнении задачи Worker разрешает прокси в следующем порядке:

1. **`task_proxies`** (per-task) — если для `task_id` есть запись в таблице `task_proxies`, используется она. Это **индивидуальный прокси конкретной задачи**, заданный при создании через `POST /api/tasks` с полями `proxy_host`/`proxy_port`.
2. **`ad_proxy_configs`** (per-ad) — если per-task прокси нет, проверяется `task.ad_id` в таблице `ad_proxy_configs`.
3. **`ProxyPool`** (общий пул) — если no per-task и per-ad прокси, берётся случайный прокси из `PROXY_LIST`.

Приоритет гарантирует, что при явном задании прокси для задачи она всегда использует один и тот же IP даже при retry (запись в `task_proxies` не меняется при requeue).
