"""Alembic env for agent-clicker (async engine via asyncpg).

Supports two migration targets:
* **internal** (default) — internal_state_dsn: runs ALL metadata (ExternalBase + InternalBase +
  ExternalMigrationsBase). Used in dev when a single DB holds everything.
* **external_migrations** — external_migrations_dsn: runs *only* ExternalMigrationsBase
  (ad_proxy_configs, task_proxies). Run via: alembic -x dsn=external_migrations upgrade head
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from agent_clicker.config import Settings
from agent_clicker.db.models import ExternalBase, ExternalMigrationsBase, InternalBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_settings = Settings()

# Determine which DSN to use based on x_dsn CLI argument
_x_dsn = context.get_x_argument(as_dictionary=True).get("dsn", "internal")

if _x_dsn == "external_migrations":
    if not _settings.external_migrations_dsn:
        raise SystemExit(
            "EXTERNAL_MIGRATIONS_DSN is not set. "
            "Pass -x dsn=external_migrations only when the env var is configured."
        )
    _dsn_async = _settings.external_migrations_dsn
    # Only ExternalMigrationsBase tables (ad_proxy_configs, task_proxies)
    target_metadata = ExternalMigrationsBase.metadata
else:
    _dsn_async = _settings.internal_state_dsn
    # Full metadata: all bases (dev mode with single DB)


    class CombinedMetadata:
        """Iterable that alembic can walk for all bases."""

        def __init__(self) -> None:
            self.tables = {
                **ExternalBase.metadata.tables,
                **InternalBase.metadata.tables,
                **ExternalMigrationsBase.metadata.tables,
            }
            self.schema = None
            self.naming_convention = ExternalBase.metadata.naming_convention
            self.info = {}

        def sorted_tables(self):  # type: ignore[no-untyped-def]
            return (
                list(ExternalBase.metadata.sorted_tables)
                + list(InternalBase.metadata.sorted_tables)
                + list(ExternalMigrationsBase.metadata.sorted_tables)
            )


    target_metadata = CombinedMetadata()

config.set_main_option("sqlalchemy.url", _dsn_async)


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
