---
description: 'agent-clicker — Команды разработки и зависимости (разделы 11-12 тех. спецификации). Загружать при работе с pyproject.toml, Dockerfile, dev-скриптами.'
applyTo: 'pyproject.toml'
---
# agent-clicker — Техническая спецификация

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
