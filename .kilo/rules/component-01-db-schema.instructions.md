---
description: 'agent-clicker — Схема БД (раздел 3 тех. спецификации). Загружать при работе с БД, моделями, миграциями.'
applyTo: '**/db/**'
---
# agent-clicker — Техническая спецификация

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
