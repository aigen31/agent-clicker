from datetime import datetime, timedelta

import pytest

from agent_clicker.domain.task import TaskFilters, TaskStatus


@pytest.mark.asyncio
async def test_create_lease_done_flow(task_repo) -> None:
    t = await task_repo.create_task(ad_id=1, link="https://example.com", description="d")
    assert t.status == TaskStatus.PENDING

    batch = await task_repo.lease_batch(worker_id="w-0", batch_size=4, lease_timeout_seconds=600)
    ids = [x.id for x in batch]
    assert t.id in ids
    leased = next(x for x in batch if x.id == t.id)
    assert leased.status == TaskStatus.IN_PROGRESS
    assert leased.attempts == 1

    await task_repo.mark_done(t.id, result={"is_successful": True}, profile={"ua": "x"})
    got = await task_repo.get_task(t.id)
    assert got is not None and got.status == TaskStatus.DONE
    assert got.result == {"is_successful": True}


@pytest.mark.asyncio
async def test_retry_backoff(task_repo) -> None:
    t = await task_repo.create_task(ad_id=2, link="https://e2.test", description="d")
    [leased] = await task_repo.lease_batch(worker_id="w", batch_size=1, lease_timeout_seconds=600)
    retry_at = datetime.utcnow() + timedelta(seconds=1)
    await task_repo.mark_failed(leased.id, error="boom", profile={"x": 1}, retry_at=retry_at)
    got = await task_repo.get_task(leased.id)
    assert got.status == TaskStatus.PENDING
    assert got.last_error == "boom"


@pytest.mark.asyncio
async def test_reclaim_expired(task_repo, engines) -> None:
    from sqlalchemy import text

    t = await task_repo.create_task(ad_id=3, link="https://e3.test", description="d")
    [leased] = await task_repo.lease_batch(worker_id="w", batch_size=1, lease_timeout_seconds=600)
    # backdate locked_at
    async with engines.internal.begin() as conn:
        await conn.execute(
            text("UPDATE task_runtime SET locked_at = now() - interval '2 hours' WHERE task_id=:i"),
            {"i": leased.id},
        )
    n = await task_repo.reclaim_expired(lease_timeout_seconds=60)
    assert n >= 1
    got = await task_repo.get_task(leased.id)
    assert got.status == TaskStatus.PENDING
    assert got.locked_at is None


@pytest.mark.asyncio
async def test_list_and_filter(task_repo) -> None:
    for i in range(3):
        await task_repo.create_task(ad_id=10 + i, link="https://e.test", description="d")
    page = await task_repo.list_tasks(filters=TaskFilters(), page=1, page_size=10)
    assert page.total >= 3


@pytest.mark.asyncio
async def test_requeue_from_terminal(task_repo) -> None:
    t = await task_repo.create_task(ad_id=4, link="https://e.test", description="d")
    [leased] = await task_repo.lease_batch(worker_id="w", batch_size=1, lease_timeout_seconds=600)
    await task_repo.mark_failed(leased.id, error="terminal", profile=None, retry_at=None)
    got = await task_repo.get_task(leased.id)
    assert got.status == TaskStatus.FAILED
    requeued = await task_repo.requeue(leased.id)
    assert requeued.status == TaskStatus.PENDING
    assert requeued.attempts == 0


@pytest.mark.asyncio
async def test_create_task_with_cookies(task_repo) -> None:
    cookies = [
        {"name": "sid", "value": "abc", "domain": ".vk.com", "path": "/",
         "secure": True, "httpOnly": False, "sameSite": "Lax"}
    ]
    t = await task_repo.create_task(
        ad_id=99, link="https://vk.com/im", description="d", cookies=cookies
    )
    got = await task_repo.get_task(t.id)
    assert got is not None
    assert got.cookies and got.cookies[0]["name"] == "sid"

    [leased] = await task_repo.lease_batch(worker_id="w", batch_size=1, lease_timeout_seconds=600)
    assert leased.cookies and leased.cookies[0]["value"] == "abc"
