---
description: 'agent-clicker — Архитектура: конфигурация (static Settings, dynamic settings). Загружать при работе с config.py.'
applyTo: '**/config.py'
---
# agent-clicker — Архитектура проекта

## 3. Configuration (`config.py`)

### 3.1 Static `Settings` (env-only)

Поля (из env / `.env`), иммутабельны после старта:
- **DB**: `external_tasks_dsn`, `internal_state_dsn`, `external_migrations_dsn` (optional)
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
