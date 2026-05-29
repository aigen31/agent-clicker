"""Pytest fixtures: spin up a local Postgres (docker compose service) for integration tests.

If `EXTERNAL_TASKS_DSN` is not set, tests requiring DB are skipped.
"""

from __future__ import annotations

import asyncio
import os
import socket
from pathlib import Path

import pytest
import pytest_asyncio

from agent_clicker.config import (
    AgentSettings,
    BrowserProfileDefaults,
    Settings,
    WorkerRuntimeSettings,
)


def _can_connect(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def settings() -> Settings:
    # In CI/dev assume docker compose postgres on localhost:5432.
    os.environ.setdefault(
        "EXTERNAL_TASKS_DSN", "postgresql+asyncpg://agent:agent@localhost:5440/agent_clicker"
    )
    os.environ.setdefault(
        "INTERNAL_STATE_DSN", "postgresql+asyncpg://agent:agent@localhost:5440/agent_clicker"
    )
    return Settings()


@pytest.fixture(scope="session")
def db_available(settings: Settings) -> bool:
    return _can_connect("localhost", 5440)


@pytest_asyncio.fixture
async def engines(settings: Settings, db_available: bool):
    if not db_available:
        pytest.skip("Postgres not available on localhost:5432")
    from agent_clicker.db.engine import build_engines, dispose_engines

    eng = build_engines(
        external_dsn=settings.external_tasks_dsn,
        internal_dsn=settings.internal_state_dsn,
    )
    yield eng
    await dispose_engines(eng)


@pytest_asyncio.fixture
async def task_repo(engines):
    from agent_clicker.db.repository import TaskRepository
    from sqlalchemy import text

    # clean tables between tests
    async with engines.external.begin() as conn:
        await conn.execute(text("DELETE FROM tasks"))
        await conn.execute(text("DELETE FROM ads"))
    async with engines.internal.begin() as conn:
        await conn.execute(text("DELETE FROM task_runtime"))
        await conn.execute(text("DELETE FROM settings"))

    return TaskRepository(
        external_session=engines.external_session,
        internal_session=engines.internal_session,
        default_max_attempts=3,
    )


@pytest_asyncio.fixture
async def settings_store(engines):
    from agent_clicker.db.repository import SettingsRepository
    from agent_clicker.settings_store import SettingsStore

    repo = SettingsRepository(engines.internal_session)
    store = SettingsStore(repo, ttl_seconds=0.0)
    await store.bootstrap(
        agent_defaults=AgentSettings(),
        browser_defaults=BrowserProfileDefaults(),
        worker_defaults=WorkerRuntimeSettings(),
    )
    return store
