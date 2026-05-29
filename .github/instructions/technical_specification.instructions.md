---
description: Техническая спецификация проекта agent-clicker — ИИ-агента, имитирующего действия реальных пользователей на сайтах. Загружать при работе над любым кодом, архитектурой, БД, конфигурацией или документацией проекта.
applyTo: '**'
---

# agent-clicker — Техническая спецификация

## 1. Описание проекта

`agent-clicker` — сервис на базе ИИ-агента (`browser-use`), который эмулирует разных пользователей (браузеры, устройства, IP-адреса) и выполняет задачи на целевых сайтах. Главная цель — **создать достоверное присутствие "реального пользователя"** на сайте.

### Ключевые принципы

- **Достоверность важнее точности.** Допускается неполное/неточное выполнение требований задачи, если это сохраняет иллюзию живого пользователя.
- **browser-use как основа.** Вся автоматизация браузера, планирование действий и имитация поведения делегируется библиотеке `browser-use` (open-source, на базе Playwright). Самостоятельная реализация «велосипедов» (кастомный Bezier-мышь, пошаговый планировщик, stealth-патчи) не допускается.
- **Анти-fingerprinting через `BrowserProfile`.** Ротация User-Agent, viewport, прокси, language, timezone — через конфигурацию `BrowserProfile` из `browser-use`.
- **Изоляция сессий.** Каждая задача исполняется с отдельным `BrowserProfile` (свежий `user_data_dir`, уникальные прокси) — нет совместного хранения cookies / localStorage между задачами.
- **Управление через Админ-панель.** Все настройки агента, браузера и воркеров доступны через веб-интерфейс на localhost. Там же — просмотр логов и мониторинг задач в реальном времени.

## 2. Технологический стек

### Язык и рантайм
- **Python 3.11+** — основной язык.
- **asyncio** — модель конкурентности.

### Автоматизация браузера и агент
- **`browser-use`** — единственная библиотека для автоматизации браузера и исполнения задач. Предоставляет:
  - Класс `Agent(task, llm, browser_profile=...)` — принимает NL-описание задачи, использует LLM для планирования и исполнения, сам управляет браузером.
  - `BrowserProfile` — полная конфигурация браузера: `headless`, `proxy` (`ProxySettings`), `user_agent`, `viewport`, `locale`, `timezone_id`, `disable_security`, `allowed_domains` и десятки других параметров.
  - Встроенная stealth-маскировка: отключение `AutomationControlled`, скрытие `navigator.webdriver`, корректный `chrome.runtime`, расширения для блокировки рекламы и cookie-баннеров.
  - Встроенные hooks: `register_new_step_callback`, `register_done_callback`, `on_step_start`, `on_step_end` — для интеграции с системой логирования и мониторинга.
  - `AgentHistoryList` — история выполнения: шаги, скриншоты, результаты, `is_successful()`.
- Прямые вызовы Playwright API (`page.click`, `page.fill` и т. п.) **запрещены** в бизнес-логике — только через `Agent` из `browser-use`.

### База данных
- **PostgreSQL 15+** — единственное хранилище состояния задач.
- **asyncpg** — асинхронный драйвер.
- **SQLAlchemy 2.x (async) + asyncpg** — ORM для репозитория.
- **Alembic** — миграции схемы.

### Прокси и сеть
- **Резидентные / мобильные прокси** (внешний провайдер, конфигурируется через env). Поддержка `http`, `https`, `socks5`.
- Ротация IP per-task через `BrowserProfile(proxy=ProxySettings(server=..., username=..., password=...))`.
- Привязка прокси к гео / таймзоне / языку профиля.

### Очередь и оркестрация
- Воркеры на `asyncio` с ограничением параллелизма (semaphore).
- Polling таблицы `tasks` через `SELECT ... FOR UPDATE SKIP LOCKED` — простая надёжная очередь без отдельного брокера.
- Опционально: **Redis** для распределённых блокировок / rate-limiting при нескольких воркер-процессах.

### Планирование действий
- Полностью делегируется `browser-use`. `Agent` принимает `task` (поле `description` из БД + URL) и самостоятельно строит и исполняет план на основе LLM (OpenAI-совместимый API, модель конфигурируется).
- Отдельный модуль `planner/` и схема шагов **не нужны**.

### Логирование и наблюдаемость
- Стандартный Python `logging` с JSON-форматтером (совместим с `browser-use`, который также использует `logging`).
- Все логи воркеров, `browser-use`-агентов и веб-сервера пишутся в единый поток и доступны в реальном времени через Админ-панель (WebSocket).
- **Sentry** (опционально) — трекинг исключений.
- Скриншоты и артефакты сохраняются `browser-use` в `./artifacts/{task_id}/`.

### Конфигурация
- **pydantic-settings** — типизированные настройки из `.env`.
- Настройки делятся на три группы (все управляемы через Админ-панель):
  - **Worker settings** — параллелизм, таймауты, retry-политика.
  - **Agent settings** — LLM-модель, `max_steps`, `use_vision`, `extend_system_message` и др. параметры `browser-use Agent`.
  - **Browser profile defaults** — `headless`, `disable_security`, `highlight_elements`, тайминги ожидания и др. дефолты `BrowserProfile`.
- `.env` — секреты (DSN PostgreSQL, прокси-провайдер, ключи LLM). Секреты из Админ-панели **не редактируются** — только через `.env`.

### Adminpanel (Веб-интерфейс)
- **FastAPI** — backend API (REST + WebSocket).
- **Jinja2** или лёгкий SPA (Vanilla JS / Alpine.js) — frontend, отдаётся через `StaticFiles`.
- Запускается как отдельный процесс (`uvicorn`) или совместно с воркером через `asyncio.gather`.
- Доступна только на `localhost` (не выставлять наружу без аутентификации).

### Качество кода
- **ruff** — линтер + форматтер.
- **mypy** в strict-режиме — статическая типизация.
- **pytest** + **pytest-asyncio** — тесты.

### Контейнеризация
- **Docker** + **docker-compose** — локальный запуск (app + postgres). В образ ставятся браузеры через `playwright install --with-deps chromium`.

## 3. Схема БД

Единственная обязательная таблица — `tasks`.

| Колонка       | Тип                     | Назначение                                                                  |
| ------------- | ----------------------- | --------------------------------------------------------------------------- |
| `id`          | `BIGSERIAL PRIMARY KEY` | Идентификатор задачи.                                                       |
| `ad_id`       | `BIGINT NOT NULL`       | Внешний идентификатор рекламы / объявления, к которому относится задача.    |
| `status`      | `task_status NOT NULL`  | Статус (ENUM, см. ниже). По умолчанию `pending`.                            |
| `description` | `TEXT NOT NULL`         | Текстовое описание задачи на сайте — передаётся напрямую в `Agent(task=…)`. |
| `link`        | `TEXT NOT NULL`         | URL целевой страницы — включается в `task` как начальная точка навигации.   |
| `created_at`  | `TIMESTAMPTZ NOT NULL`  | Время создания записи. По умолчанию `now()`.                                |
| `exec_time`   | `TIMESTAMPTZ`           | Запланированное / фактическое время исполнения (см. ниже).                  |

### ENUM `task_status`

`pending` → `scheduled` → `in_progress` → (`done` | `failed` | `skipped`).

### Уточнение бизнес-логики `exec_time`

- При создании задачи `exec_time` — **планируемое** время старта. `NULL` = «выполнить как можно скорее».
- При переходе задачи в `in_progress` воркер **обновляет** `exec_time` на фактическое время старта (`now()`).
- Историю «план vs факт» хранить в `result.scheduled_at` / `result.started_at` (JSONB).

### Рекомендуемые индексы
- `(status, exec_time)` — для выборки задач, готовых к запуску.
- `(ad_id)` — для агрегаций по рекламе.
- `(status) WHERE status IN ('pending','scheduled')` — частичный, ускоряет polling.

### Служебные колонки (добавляются миграцией поверх обязательных)

- `attempts INT NOT NULL DEFAULT 0` — счётчик попыток.
- `max_attempts INT NOT NULL DEFAULT 3`.
- `last_error TEXT` — последняя ошибка.
- `worker_id TEXT` — идентификатор воркера, взявшего задачу.
- `locked_at TIMESTAMPTZ` — visibility timeout для защиты от зависших задач.
- `profile JSONB` — снимок использованного `BrowserProfile` (UA, viewport, гео, прокси-server) для аудита.
- `result JSONB` — итог работы агента: `is_successful`, шаги, время, путь к артефактам, `AgentHistoryList`-метаданные.

## 4. Архитектура

```
                ┌──────────────────────┐        ┌──────────────────────┐
                │   tasks (Postgres)   │        │   Admin Panel        │
                └──────────┬───────────┘        │   (FastAPI / WS)     │
                           │ SELECT FOR UPDATE   │                      │
                           │ SKIP LOCKED         │  • Settings editor   │
                           ▼                     │  • Task manager      │
                  ┌─────────────────┐            │  • Live log viewer   │
                  │   Dispatcher    │◄───────────┤  • Artifact browser  │
                  └────────┬────────┘            └──────────────────────┘
                           │ Task
                           ▼
                  ┌─────────────────┐
                  │  Worker (async) │  N штук (asyncio semaphore)
                  └────────┬────────┘
                           │
            ┌──────────────┴───────────────┐
            ▼                              ▼
    ProfileFactory                    ProxyPool
    (BrowserProfile:                  (ротация прокси
     UA, viewport,                    per-task, привязка
     locale, TZ,                      к гео профиля)
     stealth-defaults)
            │                              │
            └──────────────┬───────────────┘
                           ▼
                  ┌─────────────────────────┐
                  │  browser-use Agent      │
                  │  Agent(                 │
                  │    task=desc+link,      │
                  │    llm=LLM(...),        │
                  │    browser_profile=…,   │
                  │    max_steps=…,         │
                  │    extend_system_msg=…, │
                  │    callbacks=…          │
                  │  )                      │
                  └────────────┬────────────┘
                               │ Playwright + stealth
                               ▼
                           Target site
```

### Рекомендованная структура кода

```
src/
  agent_clicker/
    __init__.py
    config.py              # pydantic-settings: WorkerSettings, AgentSettings, BrowserProfileDefaults
    db/
      models.py            # SQLAlchemy ORM-модели
      repository.py        # CRUD tasks: lease / ack / fail / watchdog
      migrations/          # alembic
    queue/
      dispatcher.py        # polling + лизинг задач
    profiles/
      factory.py           # генерация BrowserProfile (UA, viewport, locale, TZ)
    proxy/
      pool.py              # ProxyPool: выбор и ротация прокси
    browser/
      runner.py            # запуск browser-use Agent, обработка результата
    workers/
      worker.py            # Worker: связывает ProfileFactory, ProxyPool, runner
      main.py              # entrypoint: запуск воркеров + Админ-панели
    admin/
      app.py               # FastAPI-приложение Админ-панели
      routers/
        settings.py        # GET/PATCH настроек (AgentSettings, BrowserProfileDefaults, WorkerSettings)
        tasks.py           # GET/POST/DELETE задач, ручной retry
        logs.py            # WebSocket-стриминг логов
      static/              # HTML/CSS/JS фронтенд (Jinja2 templates или SPA)
    observability/
      logging.py           # настройка logging + LogBroadcastHandler для WebSocket
      artifacts.py         # сохранение скриншотов, HAR
tests/
```

## 5. Жизненный цикл задачи

1. **Создание.** Внешний источник вставляет строку в `tasks` со `status='pending'`, заполняет `ad_id`, `link`, `description`, опционально `exec_time`.

2. **Диспетчер** выбирает задачи:
   ```sql
   SELECT * FROM tasks
   WHERE status IN ('pending','scheduled')
     AND (exec_time IS NULL OR exec_time <= now())
   ORDER BY exec_time NULLS FIRST, id
   FOR UPDATE SKIP LOCKED
   LIMIT :batch;
   ```
   Переводит в `in_progress`, выставляет `worker_id`, `locked_at = now()`, инкрементит `attempts`, обновляет `exec_time = now()`.

3. **Воркер**:
   1. `ProfileFactory` → `BrowserProfile` (случайный UA из набора реальных, viewport, locale, TZ, stealth-дефолты из конфига).
   2. `ProxyPool` → прокси для данного профиля (`ProxySettings(server, username, password)`); гео прокси согласовано с locale/TZ профиля.
   3. `browser/runner.py` формирует строку задачи: `f"Перейди на {link} и выполни: {description}"`.
   4. Создаёт `Agent(task=..., llm=..., browser_profile=..., max_steps=..., extend_system_message=..., register_new_step_callback=..., register_done_callback=...)` и вызывает `history = await agent.run()`.
   5. `extend_system_message` содержит инструкцию «после основного действия поведи себя как живой пользователь: пролистай страницу, прочитай несколько секций, при наличии ссылок — перейди по 1–2 случайным внутренним; суммарное время на сайте — не менее MIN_TIME_ON_SITE_SECONDS».
   6. Callbacks (`register_new_step_callback`, `register_done_callback`) передают события шагов в систему логирования для стриминга в Админ-панель.

4. **Финал.**
   - `history.is_successful() is True` → `status='done'`, в `result` записываются: `is_successful`, число шагов, `history.final_result()`, `history.total_duration_seconds()`, путь к артефактам.
   - `history.is_successful() is False` или исключение → `status='failed'`, `last_error`. Если `attempts < max_attempts`, задача возвращается в `pending` с экспоненциальным backoff: `exec_time = now() + base * 2^attempts`.

5. **Watchdog.** Отдельная корутина ищет задачи в `in_progress` с `locked_at < now() - lease_timeout` и возвращает их в `pending` (защита от падений воркера).

## 6. Имитация человеческого поведения

Полностью обеспечивается `browser-use`. Не требует отдельной реализации:

- `browser-use` использует LLM для интерпретации страницы и выбора действий — поведение нелинейно и непредсказуемо, как у живого пользователя.
- `BrowserProfile` поддерживает `minimum_wait_page_load_time`, `wait_for_network_idle_page_load_time`, `wait_between_actions` — управляют паузами между действиями.
- Встроенные расширения (`uBlock Origin Lite`, `I still don't care about cookies`) убирают баннеры — страница выглядит «как видит её обычный пользователь».

Дополнительно через `extend_system_message` агенту передаются инструкции имитировать «залипание» на сайте (прокрутка, чтение, случайные клики по внутренним ссылкам, минимальное время на сайте).

## 7. Анти-детект профиль

Каждая задача = свежий `BrowserProfile`:

- `user_agent` — случайный из набора реальных UA (Chrome/Win, Chrome/Mac, Safari/iPhone и т. п.).
- `viewport` + `device_scale_factor` — согласованы с UA.
- `locale`, `timezone_id` — согласованы с гео прокси.
- `headless`, `disable_security` — из конфига.
- `enable_default_extensions=True` — встроенные расширения browser-use для маскировки под реального пользователя.
- `user_data_dir=None` (tmpdir) — каждая задача стартует с чистого профиля (нет переноса cookies/storage между сессиями).
- `disable_blink_features=AutomationControlled` и набор Chrome-флагов — встроены в browser-use (не нужна отдельная stealth-реализация).

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

## 9. Админ-панель (веб-интерфейс)

Доступна по адресу `http://localhost:8080` (порт конфигурируется). Запускается параллельно с воркерами в рамках одного процесса через `asyncio.gather` или как отдельный `uvicorn`-сервер.

### Разделы

#### 9.1 Настройки агента (`/settings/agent`)
Управление параметрами `browser-use Agent` (сохраняются в БД или конфиг-файле, применяются при следующей задаче):

| Параметр                | Соответствует              | Описание                                         |
| ----------------------- | -------------------------- | ------------------------------------------------ |
| `max_steps`             | `Agent(max_steps=...)`     | Максимальное число шагов агента                  |
| `use_vision`            | `Agent(use_vision=...)`    | Использовать скриншоты для анализа страницы      |
| `use_thinking`          | `Agent(use_thinking=...)`  | Цепочка рассуждений (thinking mode) у LLM        |
| `max_failures`          | `Agent(max_failures=...)`  | Порог последовательных ошибок до остановки       |
| `step_timeout`          | `Agent(step_timeout=...)`  | Таймаут одного шага (сек)                        |
| `llm_model`             | `ChatOpenAI(model=...)`    | Модель LLM                                       |
| `extend_system_message` | `Agent(extend_system_message=...)` | Доп. инструкции агенту (поведение, залипание) |
| `max_actions_per_step`  | `Agent(max_actions_per_step=...)` | Кол-во действий за один шаг LLM              |
| `enable_planning`       | `Agent(enable_planning=...)` | Включить встроенное планирование агента         |

#### 9.2 Настройки браузера (`/settings/browser`)
Управление дефолтами `BrowserProfile` (применяются ко всем новым задачам):

| Параметр                          | Соответствует `BrowserProfile`          | Описание                                       |
| --------------------------------- | --------------------------------------- | ---------------------------------------------- |
| `headless`                        | `headless`                              | Headless-режим                                 |
| `disable_security`                | `disable_security`                      | Отключить security-ограничения браузера        |
| `wait_between_actions`            | `wait_between_actions`                  | Пауза между действиями (сек)                   |
| `minimum_wait_page_load_time`     | `minimum_wait_page_load_time`           | Минимальное ожидание загрузки страницы         |
| `wait_for_network_idle_page_load_time` | `wait_for_network_idle_page_load_time` | Ожидание network idle после загрузки        |
| `highlight_elements`              | `highlight_elements`                    | Подсвечивать элементы (отладка)                |
| `enable_default_extensions`       | `enable_default_extensions`             | Включить встроенные расширения browser-use     |
| `cross_origin_iframes`            | `cross_origin_iframes`                  | Обрабатывать cross-origin iframes              |
| `max_iframes`                     | `max_iframes`                           | Лимит iframe-документов                        |

#### 9.3 Настройки воркеров (`/settings/worker`)

| Параметр                | Описание                                                            |
| ----------------------- | ------------------------------------------------------------------- |
| `worker_concurrency`    | Кол-во параллельных задач                                           |
| `lease_timeout_seconds` | Visibility timeout задачи в `in_progress`                           |
| `max_attempts`          | Максимальное число попыток                                          |
| `backoff_base_seconds`  | База экспоненциального backoff при retry                            |
| `min_time_on_site_sec`  | Минимальное время агента на сайте (передаётся через system message) |
| `max_time_on_site_sec`  | Максимальное время агента на сайте                                  |

#### 9.4 Менеджер задач (`/tasks`)
- Таблица задач с фильтрацией по `status`, `ad_id`, дате.
- Ручной запуск retry для `failed`-задач.
- Просмотр `result` и `last_error` задачи.
- Создание тестовой задачи прямо из интерфейса.
- Просмотр артефактов (скриншотов) задачи.

#### 9.5 Лог-вьювер (`/logs`)
- Реальный стриминг логов через **WebSocket** (`/ws/logs`).
- Фильтрация по уровню (`DEBUG`, `INFO`, `WARNING`, `ERROR`), воркеру, task_id.
- Буфер последних N строк (отображается при первом открытии вкладки).
- Реализуется через кастомный `logging.Handler` (`LogBroadcastHandler`), который отправляет записи всем подключённым WebSocket-клиентам.

Структура лог-сообщения (JSON):
```json
{
  "ts": "2026-05-29T12:00:00.123Z",
  "level": "INFO",
  "logger": "browser_use.Agent🅰a1b2 ⇢ 🅑 c3d4 🅣 e5",
  "task_id": "task-uuid",
  "worker_id": "worker-0",
  "msg": "📍 Step 3:"
}
```

## 10. Правила для ИИ при работе с этим репозиторием

При генерации / правке кода обязательно:

1. **Стек строго фиксирован**: Python 3.11+, asyncio, `browser-use` (open-source), PostgreSQL + asyncpg + SQLAlchemy 2.x, FastAPI, pydantic-settings, ruff, mypy strict. Не вводить Selenium, puppeteer, requests-html, собственный stealth и т. п. без явной просьбы.
2. **Весь I/O — async.** Никаких блокирующих вызовов в горячем пути воркера.
3. **Автоматизация браузера — только через `browser-use Agent`.** Прямое использование Playwright API в бизнес-логике запрещено. Playwright используется исключительно внутри `browser-use`.
4. **БД-операции — только через `db/repository.py`.** Сырой SQL допустим лишь в репозитории и миграциях.
5. **Структурное логирование:** `logger.info("task.leased", extra={"task_id": ..., "worker_id": ...})`. Без f-string логов с PII и без логирования секретов.
6. **Идемпотентность и failure-tolerance.** Любая задача должна корректно перезапускаться. Исключение внутри `agent.run()` перехватывается воркером, задача помечается `failed`, воркер не падает.
7. **Типизация.** Все публичные функции — с аннотациями, `mypy --strict` должен проходить.
8. **Конфигурация — только через `config.Settings`.** Никаких `os.environ.get(...)` россыпью по коду.
9. **Тесты.** Для нового модуля — минимум один happy-path тест (`pytest-asyncio`). В тестах `Agent` — mock через `unittest.mock`.
10. **Безопасность.** Прокси-креды, LLM-ключи, DSN — только из env, никогда в коде / логах / артефактах. Не коммитить `.env`, артефакты, скриншоты. Админ-панель слушает только на `localhost`.
11. **Настройки через Админ-панель.** Все параметры `Agent` и `BrowserProfile`, влияющие на поведение (кроме секретов), должны быть доступны для редактирования через REST API Админ-панели. Изменения применяются к следующим запускаемым задачам (без перезапуска процесса).
12. **Этика и легальность.** Не реализовывать обход CAPTCHA сторонних сервисов, обход пэйволлов, накрутку, нарушающую ToS площадок, без явного указания пользователя.

## 11. Команды разработки

```bash
# установка
uv sync                                # или: pip install -e ".[dev]"
uvx browser-use install                # установить Chromium для browser-use
# или: playwright install --with-deps chromium

# миграции
alembic upgrade head

# линт / типы / тесты
ruff check . && ruff format --check .
mypy src
pytest -q

# запуск воркеров + Админ-панели
python -m agent_clicker.workers.main

# запуск только Админ-панели
uvicorn agent_clicker.admin.app:app --host 127.0.0.1 --port 8080 --reload

# docker
docker compose up --build
```

## 12. Зависимости (pyproject.toml)

```toml
[project]
dependencies = [
    "browser-use>=0.12",         # AI browser agent
    "sqlalchemy[asyncio]>=2.0",  # ORM
    "asyncpg>=0.29",             # async PostgreSQL driver
    "alembic>=1.13",             # migrations
    "fastapi>=0.111",            # admin panel backend
    "uvicorn[standard]>=0.29",   # ASGI server
    "jinja2>=3.1",               # admin panel templates
    "python-multipart>=0.0.9",   # form data in FastAPI
    "websockets>=12.0",          # WebSocket support
    "pydantic-settings>=2.2",    # typed config from env
    "langchain-openai>=0.1",     # OpenAI-compatible LLM для browser-use
]

[project.optional-dependencies]
dev = [
    "ruff>=0.4",
    "mypy>=1.10",
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
]
```
