---
description: 'agent-clicker — Архитектура: ProfileFactory, каталоги UA/viewport/geo. Загружать при работе с profiles/.'
applyTo: '**/profiles/**'
---
# agent-clicker — Архитектура проекта

## 7. Profiles

### 7.1 `profiles/catalog.py`

Статические наборы (минимум):
- `UA_CATALOG: list[UAEntry]` — ≥20 реальных User-Agent (Chrome/Firefox/Safari × Win/Mac/iOS/Android), каждый с допустимыми viewport-пресетами.
- `GEO_LOCALE_TZ: dict[str, tuple[str, str]]` — `"US" → ("en-US", "America/New_York")`, и т.д.

### 7.2 `profiles/factory.py`

**`ProfileFactory(defaults: BrowserProfileDefaults, settings: Settings)`**:
- `build_spec(*, proxy)` → `ProfileSpec`: чистая функция — случайный UA + согласованный viewport/dpr; locale/TZ из `GEO_LOCALE_TZ[proxy.geo]` если geo задан, иначе random из набора
- `build_browser_profile(spec)` → `BrowserProfile`: ProfileSpec + BrowserProfileDefaults → `browser_use.BrowserProfile` (`user_data_dir=None` для изоляции сессий, `proxy=ProxySettings(...)` или None, все timing-параметры из defaults)

`defaults` читается из `SettingsStore` перед каждой задачей в `AgentRunner`, и `ProfileFactory` пересоздаётся либо принимает свежий snapshot — см. §11.
