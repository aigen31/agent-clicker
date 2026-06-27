"""Repositories — single I/O surface for `tasks` and `settings` / `task_runtime`."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, select, true, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_clicker.db.models import Ad, AdProxyConfig, Setting, Task, TaskProxy, TaskRuntime
from agent_clicker.domain.task import AdProxyConfigDTO, Page, TaskDTO, TaskFilters, TaskProxyConfigDTO, TaskStatus


def _now() -> datetime:
    """Naive UTC, matching the prod `TIMESTAMP WITHOUT TIME ZONE` convention."""
    return datetime.utcnow()


def _truncate(value: str | None, limit: int = 4000) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else value[: limit - 1] + "\u2026"


def _row_to_dto(task: Task, runtime: TaskRuntime | None) -> TaskDTO:
    return TaskDTO(
        id=task.id,
        ad_id=task.ad_id,
        status=task.status,
        description=task.description,
        link=task.link,
        created_at=task.created_at,
        exec_time=task.exec_time,
        attempts=runtime.attempts if runtime else 0,
        max_attempts=runtime.max_attempts if runtime else 3,
        last_error=runtime.last_error if runtime else None,
        worker_id=runtime.worker_id if runtime else None,
        locked_at=runtime.locked_at if runtime else None,
        profile=runtime.profile if runtime else None,
        result=runtime.result if runtime else None,
        cookies=runtime.cookies if runtime else None,
    )


class TaskRepository:
    """Cross-DB repository: reads `tasks` from external, runtime from internal."""

    def __init__(
        self,
        *,
        external_session: async_sessionmaker[AsyncSession],
        internal_session: async_sessionmaker[AsyncSession],
        default_max_attempts: int = 3,
    ) -> None:
        self._ext = external_session
        self._intl = internal_session
        self._default_max_attempts = default_max_attempts

    # ---------------- leasing ----------------

    async def lease_batch(
        self,
        *,
        worker_id: str,
        batch_size: int,
        lease_timeout_seconds: int,
    ) -> list[TaskDTO]:
        if batch_size <= 0:
            return []

        # 1) External: lease rows atomically.
        leased_ids: list[int] = []
        leased_tasks: list[Task] = []
        async with self._ext() as session, session.begin():
            stmt = (
                select(Task)
                .where(
                    Task.status.in_(TaskStatus.LEASABLE),
                    (Task.exec_time.is_(None)) | (Task.exec_time <= _now()),
                )
                .order_by(Task.exec_time.asc().nulls_first(), Task.id.asc())
                .with_for_update(skip_locked=True)
                .limit(batch_size)
            )
            result = await session.execute(stmt)
            tasks = list(result.scalars().all())
            if not tasks:
                return []
            ids = [t.id for t in tasks]
            await session.execute(
                update(Task)
                .where(Task.id.in_(ids))
                .values(status=TaskStatus.IN_PROGRESS, exec_time=_now())
            )
            leased_ids = ids
            leased_tasks = tasks
            for t in leased_tasks:
                t.status = TaskStatus.IN_PROGRESS

        # 2) Internal: upsert runtime rows (increment attempts).
        try:
            async with self._intl() as session, session.begin():
                existing_stmt = select(TaskRuntime).where(TaskRuntime.task_id.in_(leased_ids))
                existing = {r.task_id: r for r in (await session.execute(existing_stmt)).scalars()}
                now = _now()
                for tid in leased_ids:
                    if tid in existing:
                        rt = existing[tid]
                        rt.attempts = (rt.attempts or 0) + 1
                        rt.worker_id = worker_id
                        rt.locked_at = now
                    else:
                        session.add(
                            TaskRuntime(
                                task_id=tid,
                                attempts=1,
                                max_attempts=self._default_max_attempts,
                                worker_id=worker_id,
                                locked_at=now,
                            )
                        )
        except Exception:
            # Compensating action — release external lease back to created.
            async with self._ext() as session, session.begin():
                await session.execute(
                    update(Task)
                    .where(Task.id.in_(leased_ids))
                    .values(status=TaskStatus.CREATED)
                )
            raise

        # 3) Return DTOs.
        async with self._intl() as session:
            rt_map = {
                r.task_id: r
                for r in (
                    await session.execute(
                        select(TaskRuntime).where(TaskRuntime.task_id.in_(leased_ids))
                    )
                ).scalars()
            }
        return [_row_to_dto(t, rt_map.get(t.id)) for t in leased_tasks]

    # ---------------- transitions ----------------

    async def mark_done(
        self,
        task_id: int,
        *,
        result: dict[str, Any],
        profile: dict[str, Any],
    ) -> None:
        async with self._ext() as session, session.begin():
            await session.execute(
                update(Task)
                .where(Task.id == task_id, Task.status == TaskStatus.IN_PROGRESS)
                .values(status=TaskStatus.COMPLETED)
            )
        async with self._intl() as session, session.begin():
            await session.execute(
                update(TaskRuntime)
                .where(TaskRuntime.task_id == task_id)
                .values(result=result, profile=profile, locked_at=None, last_error=None)
            )

    async def mark_failed(
        self,
        task_id: int,
        *,
        error: str | None,
        profile: dict[str, Any] | None,
        retry_at: datetime | None,
    ) -> None:
        err = _truncate(error)
        if retry_at is not None:
            # backoff retry → leasable again (pending)
            async with self._ext() as session, session.begin():
                await session.execute(
                    update(Task)
                    .where(Task.id == task_id, Task.status == TaskStatus.IN_PROGRESS)
                    .values(status=TaskStatus.PENDING, exec_time=retry_at)
                )
            async with self._intl() as session, session.begin():
                await session.execute(
                    update(TaskRuntime)
                    .where(TaskRuntime.task_id == task_id)
                    .values(
                        last_error=err,
                        profile=profile,
                        locked_at=None,
                        worker_id=None,
                    )
                )
        else:
            async with self._ext() as session, session.begin():
                await session.execute(
                    update(Task)
                    .where(Task.id == task_id, Task.status == TaskStatus.IN_PROGRESS)
                    .values(status=TaskStatus.FAILED)
                )
            async with self._intl() as session, session.begin():
                await session.execute(
                    update(TaskRuntime)
                    .where(TaskRuntime.task_id == task_id)
                    .values(last_error=err, profile=profile, locked_at=None)
                )

    async def mark_ignored(self, task_id: int, *, reason: str) -> None:
        async with self._ext() as session, session.begin():
            await session.execute(
                update(Task)
                .where(Task.id == task_id, Task.status == TaskStatus.IN_PROGRESS)
                .values(status=TaskStatus.IGNOREN)
            )
        async with self._intl() as session, session.begin():
            await session.execute(
                update(TaskRuntime)
                .where(TaskRuntime.task_id == task_id)
                .values(last_error=_truncate(reason), locked_at=None)
            )

    async def reclaim_expired(self, *, lease_timeout_seconds: int) -> int:
        """Watchdog: release in_progress tasks whose lease expired."""
        threshold = _now() - timedelta(seconds=lease_timeout_seconds)
        async with self._intl() as session, session.begin():
            stale = (
                await session.execute(
                    select(TaskRuntime.task_id).where(
                        TaskRuntime.locked_at.is_not(None),
                        TaskRuntime.locked_at < threshold,
                    )
                )
            ).scalars().all()
        if not stale:
            return 0
        async with self._ext() as session, session.begin():
            res = await session.execute(
                update(Task)
                .where(Task.id.in_(stale), Task.status == TaskStatus.IN_PROGRESS)
                .values(status=TaskStatus.PENDING)
            )
            reclaimed = res.rowcount or 0
        async with self._intl() as session, session.begin():
            await session.execute(
                update(TaskRuntime)
                .where(TaskRuntime.task_id.in_(stale))
                .values(locked_at=None, worker_id=None)
            )
        return int(reclaimed)

    # ---------------- admin queries ----------------

    async def list_tasks(
        self, *, filters: TaskFilters, page: int, page_size: int
    ) -> Page[TaskDTO]:
        page = max(1, page)
        page_size = max(1, min(page_size, 200))
        offset = (page - 1) * page_size
        conditions = []
        if filters.status:
            conditions.append(Task.status == filters.status)
        if filters.ad_id is not None:
            conditions.append(Task.ad_id == filters.ad_id)
        if filters.created_from:
            conditions.append(Task.created_at >= filters.created_from)
        if filters.created_to:
            conditions.append(Task.created_at <= filters.created_to)

        async with self._ext() as session:
            where_clause = and_(true(), *conditions)
            total = int(
                (
                    await session.execute(
                        select(func.count()).select_from(Task).where(where_clause)
                    )
                ).scalar_one()
            )
            stmt = (
                select(Task)
                .where(where_clause)
                .order_by(Task.id.desc())
                .offset(offset)
                .limit(page_size)
            )
            tasks = list((await session.execute(stmt)).scalars().all())

        ids = [t.id for t in tasks]
        rt_map: dict[int, TaskRuntime] = {}
        if ids:
            async with self._intl() as session:
                rt_map = {
                    r.task_id: r
                    for r in (
                        await session.execute(
                            select(TaskRuntime).where(TaskRuntime.task_id.in_(ids))
                        )
                    ).scalars()
                }
        items = [_row_to_dto(t, rt_map.get(t.id)) for t in tasks]
        return Page(items=items, total=total, page=page, page_size=page_size)

    async def get_task(self, task_id: int) -> TaskDTO | None:
        async with self._ext() as session:
            task = (
                await session.execute(select(Task).where(Task.id == task_id))
            ).scalar_one_or_none()
        if not task:
            return None
        async with self._intl() as session:
            rt = (
                await session.execute(
                    select(TaskRuntime).where(TaskRuntime.task_id == task_id)
                )
            ).scalar_one_or_none()
        return _row_to_dto(task, rt)

    async def create_task(
        self,
        *,
        ad_id: int,
        link: str,
        description: str,
        exec_time: datetime | None = None,
        max_attempts: int | None = None,
        cookies: list[dict[str, Any]] | None = None,
    ) -> TaskDTO:
        """**Dev-only**: requires INSERT privilege on tasks. Never call in prod."""
        async with self._ext() as session, session.begin():
            # ensure ad exists (dev convenience)
            exists = (
                await session.execute(select(Ad.id).where(Ad.id == ad_id))
            ).scalar_one_or_none()
            if exists is None:
                session.add(Ad(id=ad_id, title=f"dev-ad-{ad_id}"))
                await session.flush()
            task = Task(
                ad_id=ad_id,
                status=TaskStatus.CREATED,
                description=description,
                link=link,
                exec_time=exec_time,
            )
            session.add(task)
            await session.flush()
            task_id = task.id
        async with self._intl() as session, session.begin():
            session.add(
                TaskRuntime(
                    task_id=task_id,
                    attempts=0,
                    max_attempts=max_attempts or self._default_max_attempts,
                    cookies=cookies or None,
                )
            )
        got = await self.get_task(task_id)
        assert got is not None
        return got

    async def delete_task(self, task_id: int) -> bool:
        """**Dev-only**: requires DELETE privilege on tasks."""
        async with self._ext() as session, session.begin():
            res = await session.execute(delete(Task).where(Task.id == task_id))
            removed = (res.rowcount or 0) > 0
        async with self._intl() as session, session.begin():
            await session.execute(delete(TaskRuntime).where(TaskRuntime.task_id == task_id))
        return removed

    async def requeue(self, task_id: int) -> TaskDTO | None:
        async with self._ext() as session, session.begin():
            await session.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.status.in_(TaskStatus.TERMINAL),
                )
                .values(status=TaskStatus.CREATED, exec_time=None)
            )
        async with self._intl() as session, session.begin():
            await session.execute(
                update(TaskRuntime)
                .where(TaskRuntime.task_id == task_id)
                .values(attempts=0, last_error=None, locked_at=None, worker_id=None)
            )
        return await self.get_task(task_id)


class SettingsRepository:
    def __init__(self, internal_session: async_sessionmaker[AsyncSession]) -> None:
        self._intl = internal_session

    async def get(self, key: str) -> dict[str, Any] | None:
        async with self._intl() as session:
            row = (
                await session.execute(select(Setting).where(Setting.key == key))
            ).scalar_one_or_none()
            return dict(row.value) if row else None

    async def get_all(self) -> dict[str, dict[str, Any]]:
        async with self._intl() as session:
            rows = (await session.execute(select(Setting))).scalars().all()
        return {r.key: dict(r.value) for r in rows}

    async def upsert(self, key: str, value: dict[str, Any]) -> None:
        async with self._intl() as session, session.begin():
            stmt = pg_insert(Setting).values(key=key, value=value)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Setting.key],
                set_={"value": value, "updated_at": func.now()},
            )
            await session.execute(stmt)


class AdProxyRepository:
    """CRUD for per-ad_id proxy configurations (internal table)."""

    def __init__(self, internal_session: async_sessionmaker[AsyncSession]) -> None:
        self._intl = internal_session

    async def get_by_ad_id(self, ad_id: int) -> AdProxyConfigDTO | None:
        async with self._intl() as session:
            row = (
                await session.execute(
                    select(AdProxyConfig).where(AdProxyConfig.ad_id == ad_id)
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return AdProxyConfigDTO(
                ad_id=row.ad_id,
                proxy_host=row.proxy_host,
                proxy_port=row.proxy_port,
                proxy_login=row.proxy_login,
                proxy_password=row.proxy_password,
            )

    async def list_all(self) -> list[AdProxyConfigDTO]:
        async with self._intl() as session:
            rows = (
                await session.execute(
                    select(AdProxyConfig).order_by(AdProxyConfig.ad_id.asc())
                )
            ).scalars().all()
        return [
            AdProxyConfigDTO(
                ad_id=r.ad_id,
                proxy_host=r.proxy_host,
                proxy_port=r.proxy_port,
                proxy_login=r.proxy_login,
                proxy_password=r.proxy_password,
            )
            for r in rows
        ]

    async def upsert(
        self,
        *,
        ad_id: int,
        proxy_host: str,
        proxy_port: int,
        proxy_login: str | None = None,
        proxy_password: str | None = None,
    ) -> AdProxyConfigDTO:
        async with self._intl() as session, session.begin():
            stmt = pg_insert(AdProxyConfig).values(
                ad_id=ad_id,
                proxy_host=proxy_host,
                proxy_port=proxy_port,
                proxy_login=proxy_login,
                proxy_password=proxy_password,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[AdProxyConfig.ad_id],
                set_={
                    "proxy_host": proxy_host,
                    "proxy_port": proxy_port,
                    "proxy_login": proxy_login,
                    "proxy_password": proxy_password,
                    "updated_at": func.now(),
                },
            )
            await session.execute(stmt)
        dto = await self.get_by_ad_id(ad_id)
        assert dto is not None
        return dto

    async def delete(self, ad_id: int) -> bool:
        async with self._intl() as session, session.begin():
            res = await session.execute(
                delete(AdProxyConfig).where(AdProxyConfig.ad_id == ad_id)
            )
            return (res.rowcount or 0) > 0


class TaskProxyRepository:
    """CRUD for per-task_id proxy configurations (internal table)."""

    def __init__(self, internal_session: async_sessionmaker[AsyncSession]) -> None:
        self._intl = internal_session

    async def get_by_task_id(self, task_id: int) -> TaskProxyConfigDTO | None:
        async with self._intl() as session:
            row = (
                await session.execute(
                    select(TaskProxy).where(TaskProxy.task_id == task_id)
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return TaskProxyConfigDTO(
                task_id=row.task_id,
                proxy_host=row.proxy_host,
                proxy_port=row.proxy_port,
                proxy_login=row.proxy_login,
                proxy_password=row.proxy_password,
            )

    async def list_all(self) -> list[TaskProxyConfigDTO]:
        async with self._intl() as session:
            rows = (
                await session.execute(
                    select(TaskProxy).order_by(TaskProxy.task_id.desc())
                )
            ).scalars().all()
        return [
            TaskProxyConfigDTO(
                task_id=r.task_id,
                proxy_host=r.proxy_host,
                proxy_port=r.proxy_port,
                proxy_login=r.proxy_login,
                proxy_password=r.proxy_password,
            )
            for r in rows
        ]

    async def upsert(
        self,
        *,
        task_id: int,
        proxy_host: str,
        proxy_port: int,
        proxy_login: str | None = None,
        proxy_password: str | None = None,
    ) -> TaskProxyConfigDTO:
        async with self._intl() as session, session.begin():
            stmt = pg_insert(TaskProxy).values(
                task_id=task_id,
                proxy_host=proxy_host,
                proxy_port=proxy_port,
                proxy_login=proxy_login,
                proxy_password=proxy_password,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[TaskProxy.task_id],
                set_={
                    "proxy_host": proxy_host,
                    "proxy_port": proxy_port,
                    "proxy_login": proxy_login,
                    "proxy_password": proxy_password,
                    "updated_at": func.now(),
                },
            )
            await session.execute(stmt)
        dto = await self.get_by_task_id(task_id)
        assert dto is not None
        return dto

    async def delete(self, task_id: int) -> bool:
        async with self._intl() as session, session.begin():
            res = await session.execute(
                delete(TaskProxy).where(TaskProxy.task_id == task_id)
            )
            return (res.rowcount or 0) > 0


__all__ = ["TaskRepository", "SettingsRepository", "AdProxyRepository", "TaskProxyRepository"]
