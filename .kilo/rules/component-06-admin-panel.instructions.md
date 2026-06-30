---
description: 'agent-clicker — Админ-панель (раздел 9 тех. спецификации). Загружать при работе с admin/, роутерами, шаблонами, WebSocket логов.'
applyTo: '**/admin/**'
---
# agent-clicker — Техническая спецификация

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
