# agent-clicker

AI agent that emulates real users on websites. See [docs/service-overview.md](docs/service-overview.md), [.github/instructions/technical_specification.instructions.md](.github/instructions/technical_specification.instructions.md), and [.github/instructions/architecture.instructions.md](.github/instructions/architecture.instructions.md).

## Two databases

The service speaks to **two** Postgres instances (they may point at the same physical DB in dev):

* `EXTERNAL_TASKS_DSN` — production `tasks` table. Service has only `SELECT` + `UPDATE` on it; never run migrations or DDL there.
* `INTERNAL_STATE_DSN` — service-owned DB holding `task_runtime` (attempts, lease, last_error, profile, result) and `settings` (dynamic settings).

`alembic upgrade head` creates the internal tables. In dev it also creates `tasks` + `ads` stubs so you can run end-to-end locally; in prod those statements are skipped because the tables already exist.

## Quickstart (dev)

```bash
cp .env.example .env
docker compose up -d postgres
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -e ".[dev]" psycopg2-binary
alembic upgrade head
python -m agent_clicker
```

Admin panel: http://127.0.0.1:8088

## Pointing at production tasks DB

```bash
EXTERNAL_TASKS_DSN=postgresql+asyncpg://tasks_user:***@<prod-host>:5433/rsya_boost \
INTERNAL_STATE_DSN=postgresql+asyncpg://agent:agent@localhost:5440/agent_clicker \
ENABLE_TASK_MUTATIONS=false \
python -m agent_clicker
```

`ENABLE_TASK_MUTATIONS=false` is **mandatory** in production — the prod DB grants no INSERT/DELETE on `tasks`, and the flag returns `403` from the admin POST/DELETE endpoints so operators can't accidentally try.

## Tests

```bash
pytest -q          # 14 tests (5 unit + 9 integration). Integration needs the dev Postgres on :5440.
```
