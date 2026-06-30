---
description: 'agent-clicker — Анти-детект профиль (раздел 7 тех. спецификации). Загружать при работе с ProfileFactory, BrowserProfile.'
applyTo: '**/profiles/**'
---
# agent-clicker — Техническая спецификация

## 7. Анти-детект профиль

Каждая задача = свежий `BrowserProfile`:

- `user_agent` — случайный из набора реальных UA (Chrome/Win, Chrome/Mac, Safari/iPhone и т. п.).
- `viewport` + `device_scale_factor` — согласованы с UA.
- `locale`, `timezone_id` — согласованы с гео прокси.
- `headless`, `disable_security` — из конфига.
- `enable_default_extensions=True` — встроенные расширения browser-use для маскировки под реального пользователя.
- `user_data_dir=None` (tmpdir) — каждая задача стартует с чистого профиля (нет переноса cookies/storage между сессиями).
- `disable_blink_features=AutomationControlled` и набор Chrome-флагов — встроены в browser-use (не нужна отдельная stealth-реализация).
