---
description: 'agent-clicker — Конфигурация через env (раздел 8 тех. спецификации). Загружать при работе с config.py, .env, Settings.'
applyTo: '**/config.py'
---
# agent-clicker — Техническая спецификация

## 8. Конфигурация (env)

```env
# База данных
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/agent_clicker

# Воркеры
WORKER_CONCURRENCY=4
LEASE_TIMEOUT_SECONDS=600
MAX_ATTEMPTS=3
BACKOFF_BASE_SECONDS=30

# Прокси
PROXY_PROVIDER_URL=...
PROXY_PROVIDER_TOKEN=...

# LLM
LLM_API_KEY=...
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1   # опционально, для OpenAI-совместимых провайдеров

# browser-use Agent defaults (переопределяются через Админ-панель)
AGENT_MAX_STEPS=50
AGENT_USE_VISION=true
AGENT_USE_THINKING=true
AGENT_MAX_FAILURES=5
AGENT_STEP_TIMEOUT=180
MIN_TIME_ON_SITE_SECONDS=30
MAX_TIME_ON_SITE_SECONDS=180

# Browser profile defaults (переопределяются через Админ-панель)
BROWSER_HEADLESS=true
BROWSER_DISABLE_SECURITY=false
BROWSER_WAIT_BETWEEN_ACTIONS=0.5
BROWSER_MINIMUM_WAIT_PAGE_LOAD=0.5
BROWSER_WAIT_NETWORK_IDLE=1.0

# Артефакты и логи
ARTIFACTS_DIR=./artifacts
LOG_LEVEL=INFO

# Админ-панель
ADMIN_HOST=127.0.0.1
ADMIN_PORT=8080
```
