---
description: 'agent-clicker — Техническая спецификация проекта. Содержит ссылки на компоненты по разделам. Загружается при работе с любым кодом, архитектурой, БД, конфигурацией или документацией.'
applyTo: '**'
---

Техспецификация разбита на компоненты для экономии контекста. Каждый компонент загружается автоматически при работе с соответствующими файлами.

- [**component-00-overview**](./component-00-overview.instructions.md) — Описание проекта, ключевые принципы, технологический стек (§1-2).
- [**component-01-db-schema**](./component-01-db-schema.instructions.md) — Схема БД, колонки, индексы, ENUM (§3).
- [**component-02-lifecycle**](./component-02-lifecycle.instructions.md) — Жизненный цикл задачи, диспетчер, воркер, watchdog (§5).
- [**component-03-human-behavior**](./component-03-human-behavior.instructions.md) — Имитация человеческого поведения (§6).
- [**component-04-anti-detect**](./component-04-anti-detect.instructions.md) — Анти-детект профиль, BrowserProfile (§7).
- [**component-05-configuration**](./component-05-configuration.instructions.md) — Конфигурация через env, переменные окружения (§8).
- [**component-06-admin-panel**](./component-06-admin-panel.instructions.md) — Админ-панель, роутеры, настройки, логи (§9).
- [**component-07-ai-rules**](./component-07-ai-rules.instructions.md) — Правила для ИИ при работе с репозиторием (§10).
- [**component-08-development**](./component-08-development.instructions.md) — Команды разработки и зависимости pyproject.toml (§11-12).

> **Section 4 (Архитектура)** вынесен в отдельный файл [`architecture.instructions.md`](./architecture.instructions.md).
