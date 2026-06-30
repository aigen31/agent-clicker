---
description: 'agent-clicker — Жизненный цикл задачи (раздел 5 тех. спецификации). Загружать при работе с очередью, диспетчером, воркерами, watchdog.'
applyTo: '**/queue/**'
---
# agent-clicker — Техническая спецификация

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
