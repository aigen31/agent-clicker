"""Alembic env for agent-clicker (async engine via asyncpg)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from agent_clicker.config import Settings
from agent_clicker.db.models import ExternalBase, InternalBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_settings = Settings()
_dsn_async = _settings.internal_state_dsn

config.set_main_option("sqlalchemy.url", _dsn_async)


class CombinedMetadata:
    """Iterable that alembic can walk for both bases."""

    def __init__(self) -> None:
        self.tables = {**ExternalBase.metadata.tables, **InternalBase.metadata.tables}
        self.schema = None
        self.naming_convention = ExternalBase.metadata.naming_convention
        self.info = {}

    def sorted_tables(self):  # type: ignore[no-untyped-def]
        return list(ExternalBase.metadata.sorted_tables) + list(InternalBase.metadata.sorted_tables)


target_metadata = CombinedMetadata()


def run_migrations_offline() -> None:
    context.configure(
        url=_dsn_async,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)  # type: ignore[arg-type]
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(_dsn_async, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
