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
    external_session: async_sessionmaker[AsyncSession]
    internal_session: async_sessionmaker[AsyncSession]


def build_engines(*, external_dsn: str, internal_dsn: str) -> Engines:
    ext = create_async_engine(external_dsn, pool_pre_ping=True, pool_size=5, max_overflow=5)
    if external_dsn == internal_dsn:
        intl = ext
    else:
        intl = create_async_engine(internal_dsn, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return Engines(
        external=ext,
        internal=intl,
        external_session=async_sessionmaker(ext, expire_on_commit=False, class_=AsyncSession),
        internal_session=async_sessionmaker(intl, expire_on_commit=False, class_=AsyncSession),
    )


async def dispose_engines(engines: Engines) -> None:
    await engines.external.dispose()
    if engines.internal is not engines.external:
        await engines.internal.dispose()
