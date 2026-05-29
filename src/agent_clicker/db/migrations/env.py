"""Alembic env for agent-clicker (sync engine — alembic doesn't need async)."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from agent_clicker.config import Settings
from agent_clicker.db.models import ExternalBase, InternalBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Combined metadata for autogenerate (both schemas live in same physical DB in dev).
_settings = Settings()
_dsn_async = _settings.internal_state_dsn
_dsn_sync = _dsn_async.replace("+asyncpg", "+psycopg2") if "+asyncpg" in _dsn_async else _dsn_async
# psycopg2 may not be installed; fall back to plain psycopg if available
try:
    import psycopg2  # noqa: F401
except ImportError:
    _dsn_sync = _dsn_async.replace("+asyncpg", "")

config.set_main_option("sqlalchemy.url", _dsn_sync)


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
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
