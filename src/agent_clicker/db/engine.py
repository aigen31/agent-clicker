"""Async SQLAlchemy engines and session factories — two DBs (external tasks + internal state)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

@dataclass(frozen=True, slots=True)
class Engines:
    external: AsyncEngine
    internal: AsyncEngine
    external_migrations: AsyncEngine | None
    external_session: async_sessionmaker[AsyncSession]
    internal_session: async_sessionmaker[AsyncSession]
    external_migrations_session: async_sessionmaker[AsyncSession] | None


def build_engines(*, external_dsn: str, internal_dsn: str, external_migrations_dsn: str | None = None) -> Engines:
    ext = create_async_engine(external_dsn, pool_pre_ping=True, pool_size=5, max_overflow=5)
    if external_dsn == internal_dsn:
        intl = ext
    else:
        intl = create_async_engine(internal_dsn, pool_pre_ping=True, pool_size=5, max_overflow=5)
    
    # Handle optional external migrations database
    ext_migrations = None
    ext_migrations_session = None
    if external_migrations_dsn is not None and external_migrations_dsn != "":
        if external_migrations_dsn == external_dsn:
            ext_migrations = ext
        elif external_migrations_dsn == internal_dsn:
            ext_migrations = intl
        else:
            ext_migrations = create_async_engine(external_migrations_dsn, pool_pre_ping=True, pool_size=5, max_overflow=5)
        
        ext_migrations_session = async_sessionmaker(
            ext_migrations, expire_on_commit=False, class_=AsyncSession
        )
    
    return Engines(
        external=ext,
        internal=intl,
        external_migrations=ext_migrations,
        external_session=async_sessionmaker(ext, expire_on_commit=False, class_=AsyncSession),
        internal_session=async_sessionmaker(intl, expire_on_commit=False, class_=AsyncSession),
        external_migrations_session=ext_migrations_session,
    )


async def dispose_engines(engines: Engines) -> None:
    await engines.external.dispose()
    if engines.internal is not engines.external:
        await engines.internal.dispose()
    if engines.external_migrations is not None and engines.external_migrations is not engines.external and engines.external_migrations is not engines.internal:
        await engines.external_migrations.dispose()
