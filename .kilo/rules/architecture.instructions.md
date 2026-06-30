---
description: Подробная архитектура проекта agent-clicker — структура модулей, классов, компонентов, контрактов и потоков данных. Загружается при проектировании, реализации и ревью кода любого компонента сервиса.
applyTo: '**'
---

Подробная архитектура разбита на компоненты для экономии контекста. Каждый компонент загружается автоматически при работе с соответствующими файлами.

- [**component-arch-00-overview**](./component-arch-00-overview.instructions.md) — Production-реальность, общие принципы, структура репозитория, flow задачи, best practices, уточнения, чеклист (§0-1, §15, §17-19).
- [**component-arch-01-domain**](./component-arch-01-domain.instructions.md) — Domain-слой: DTO, enums, value-objects (§2).
- [**component-arch-02-configuration**](./component-arch-02-configuration.instructions.md) — Static Settings и Dynamic settings (§3).
- [**component-arch-03-db**](./component-arch-03-db.instructions.md) — DB-слой: модели, репозитории, миграции, SettingsStore (§4-5).
- [**component-arch-04-proxy**](./component-arch-04-proxy.instructions.md) — ProxyPool, приоритет резолвинга прокси (§6).
- [**component-arch-05-profiles**](./component-arch-05-profiles.instructions.md) — ProfileFactory, каталоги UA/viewport/geo (§7).
- [**component-arch-06-llm**](./component-arch-06-llm.instructions.md) — LLM factory, ChatOpenAI (§8).
- [**component-arch-07-browser**](./component-arch-07-browser.instructions.md) — AgentRunner, callbacks (§9).
- [**component-arch-08-queue-workers**](./component-arch-08-queue-workers.instructions.md) — Dispatcher, Watchdog, Worker, WorkerPool (§10-11).
- [**component-arch-09-observability**](./component-arch-09-observability.instructions.md) — Логирование, LogBroadcaster, ArtifactStore (§12).
- [**component-arch-10-admin**](./component-arch-10-admin.instructions.md) — Admin Panel: app, routers, frontend, security (§13).
- [**component-arch-11-composition-container**](./component-arch-11-composition-container.instructions.md) — Composition root (main.py), контейнерное окружение (§14, §16).
