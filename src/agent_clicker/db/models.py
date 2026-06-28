"""SQLAlchemy ORM models.

Two logical DBs (may point to the same physical DB in dev):
* **external** (`tasks`, `ads`) — production schema, owned by the data provider.
  Service has only SELECT + UPDATE on `tasks`. **Never** write migrations that
  ALTER this table. In dev, `ads` and `tasks` are created by alembic so we can
  run end-to-end locally.
* **internal** (`task_runtime`, `settings`) — owned by this service.
* **external_migrations** (tables like `ad_proxy_configs`, `task_proxies`) — 
  optional, can be in external DB if user has appropriate permissions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ExternalBase(DeclarativeBase):
    """Base for tables of the external (provider-owned) DB."""


class InternalBase(DeclarativeBase):
    """Base for tables of the internal (service-owned) DB."""


class ExternalMigrationsBase(DeclarativeBase):
    """Base for tables that can be in external DB with appropriate permissions."""
    pass


# ----------------- external (mirrors production) -----------------


class Ad(ExternalBase):
    """Minimal `ads` stub — exists only so that dev DB satisfies the FK on tasks."""

    __tablename__ = "ads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)


class Task(ExternalBase):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_status_exec_time", "status", "exec_time"),
        Index(
            "ix_tasks_ready",
            "exec_time",
            postgresql_where="status IN ('created','pending')",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(Integer, ForeignKey("ads.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )
    exec_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


# ----------------- internal (service-owned) -----------------


class TaskRuntime(InternalBase):
    """Service-owned runtime state, keyed by external task id."""

    __tablename__ = "task_runtime"

    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    cookies: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_runtime_locked_at", "locked_at"),)


class Setting(InternalBase):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ----------------- external_migrations (optional external tables) -----------------


class AdProxyConfig(ExternalMigrationsBase):
    """Per-ad_id proxy configuration for automatic proxy selection.
    
    Can be in external DB if user has appropriate permissions.
    """

    __tablename__ = "ad_proxy_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    proxy_host: Mapped[str] = mapped_column(String, nullable=False)
    proxy_port: Mapped[int] = mapped_column(Integer, nullable=False)
    proxy_login: Mapped[str | None] = mapped_column(String, nullable=True)
    proxy_password: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TaskProxy(ExternalMigrationsBase):
    """Per-task proxy configuration, keyed by task_id.
    
    Can be in external DB if user has appropriate permissions.
    """

    __tablename__ = "task_proxies"

    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    proxy_host: Mapped[str] = mapped_column(String, nullable=False)
    proxy_port: Mapped[int] = mapped_column(Integer, nullable=False)
    proxy_login: Mapped[str | None] = mapped_column(String, nullable=True)
    proxy_password: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ExternalBase(DeclarativeBase):
    """Base for tables of the external (provider-owned) DB."""


class InternalBase(DeclarativeBase):
    """Base for tables of the internal (service-owned) DB."""


# ----------------- external (mirrors production) -----------------


class Ad(ExternalBase):
    """Minimal `ads` stub — exists only so that dev DB satisfies the FK on tasks."""

    __tablename__ = "ads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)


class Task(ExternalBase):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_status_exec_time", "status", "exec_time"),
        Index(
            "ix_tasks_ready",
            "exec_time",
            postgresql_where="status IN ('created','pending')",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(Integer, ForeignKey("ads.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )
    exec_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


# ----------------- internal (service-owned) -----------------


class TaskRuntime(InternalBase):
    """Service-owned runtime state, keyed by external task id."""

    __tablename__ = "task_runtime"

    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    cookies: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_runtime_locked_at", "locked_at"),)


class AdProxyConfig(InternalBase):
    """Per-ad_id proxy configuration for automatic proxy selection."""

    __tablename__ = "ad_proxy_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    proxy_host: Mapped[str] = mapped_column(String, nullable=False)
    proxy_port: Mapped[int] = mapped_column(Integer, nullable=False)
    proxy_login: Mapped[str | None] = mapped_column(String, nullable=True)
    proxy_password: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TaskProxy(InternalBase):
    """Per-task proxy configuration, keyed by task_id."""

    __tablename__ = "task_proxies"

    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    proxy_host: Mapped[str] = mapped_column(String, nullable=False)
    proxy_port: Mapped[int] = mapped_column(Integer, nullable=False)
    proxy_login: Mapped[str | None] = mapped_column(String, nullable=True)
    proxy_password: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Setting(InternalBase):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )
