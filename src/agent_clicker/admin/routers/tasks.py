"""Tasks REST router."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from agent_clicker.admin.dependencies import get_task_repo, require_mutations
from agent_clicker.admin.schemas import CreateTaskRequest, PageOut, TaskOut
from agent_clicker.browser.cookies import coerce_cookies
from agent_clicker.db.repository import TaskRepository
from agent_clicker.domain.task import TaskFilters

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=PageOut[TaskOut])
async def list_tasks(
    repo: TaskRepository = Depends(get_task_repo),
    status_: str | None = Query(default=None, alias="status"),
    ad_id: int | None = None,
    created_from: datetime | None = Query(default=None, alias="from"),
    created_to: datetime | None = Query(default=None, alias="to"),
    page: int = 1,
    page_size: int = 50,
) -> PageOut[TaskOut]:
    pg = await repo.list_tasks(
        filters=TaskFilters(
            status=status_,
            ad_id=ad_id,
            created_from=created_from,
            created_to=created_to,
        ),
        page=page,
        page_size=page_size,
    )
    return PageOut[TaskOut](
        items=[TaskOut.from_dto(t) for t in pg.items],
        total=pg.total,
        page=pg.page,
        page_size=pg.page_size,
    )


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: int, repo: TaskRepository = Depends(get_task_repo)) -> TaskOut:
    dto = await repo.get_task(task_id)
    if not dto:
        raise HTTPException(status_code=404, detail="task not found")
    return TaskOut.from_dto(dto)


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: CreateTaskRequest,
    repo: TaskRepository = Depends(get_task_repo),
    _: None = Depends(require_mutations),
) -> TaskOut:
    dto = await repo.create_task(
        ad_id=body.ad_id,
        link=body.link,
        description=body.description,
        exec_time=body.exec_time,
        max_attempts=body.max_attempts,
        cookies=coerce_cookies(body.cookies, url=body.link) or None,
    )
    return TaskOut.from_dto(dto)


@router.post("/{task_id}/retry", response_model=TaskOut)
async def retry_task(task_id: int, repo: TaskRepository = Depends(get_task_repo)) -> TaskOut:
    dto = await repo.requeue(task_id)
    if not dto:
        raise HTTPException(status_code=404, detail="task not found")
    return TaskOut.from_dto(dto)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    repo: TaskRepository = Depends(get_task_repo),
    _: None = Depends(require_mutations),
) -> None:
    removed = await repo.delete_task(task_id)
    if not removed:
        raise HTTPException(status_code=404, detail="task not found")
