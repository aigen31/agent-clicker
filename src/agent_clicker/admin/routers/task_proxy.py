"""Task-proxy-config REST router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agent_clicker.admin.dependencies import get_task_proxy_repo
from agent_clicker.admin.schemas import TaskProxyConfigOut, TaskProxyConfigUpsert
from agent_clicker.db.repository import TaskProxyRepository

router = APIRouter(prefix="/api/task-proxy", tags=["task-proxy"])


@router.get("", response_model=list[TaskProxyConfigOut])
async def list_configs(repo: TaskProxyRepository = Depends(get_task_proxy_repo)) -> list[TaskProxyConfigOut]:
    dtos = await repo.list_all()
    return [TaskProxyConfigOut.from_dto(d) for d in dtos]


@router.get("/{task_id}", response_model=TaskProxyConfigOut)
async def get_config(
    task_id: int, repo: TaskProxyRepository = Depends(get_task_proxy_repo)
) -> TaskProxyConfigOut:
    dto = await repo.get_by_task_id(task_id)
    if dto is None:
        raise HTTPException(status_code=404, detail="task proxy config not found")
    return TaskProxyConfigOut.from_dto(dto)


@router.put("/{task_id}", response_model=TaskProxyConfigOut)
async def upsert_config(
    task_id: int,
    body: TaskProxyConfigUpsert,
    repo: TaskProxyRepository = Depends(get_task_proxy_repo),
) -> TaskProxyConfigOut:
    dto = await repo.upsert(
        task_id=task_id,
        proxy_host=body.proxy_host,
        proxy_port=body.proxy_port,
        proxy_login=body.proxy_login,
        proxy_password=body.proxy_password,
    )
    return TaskProxyConfigOut.from_dto(dto)


@router.delete("/{task_id}", status_code=204)
async def delete_config(
    task_id: int, repo: TaskProxyRepository = Depends(get_task_proxy_repo)
) -> None:
    removed = await repo.delete(task_id)
    if not removed:
        raise HTTPException(status_code=404, detail="task proxy config not found")
