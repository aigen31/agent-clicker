"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from agent_clicker.admin.dependencies import get_task_repo
from agent_clicker.db.repository import TaskRepository

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz(repo: TaskRepository = Depends(get_task_repo)) -> dict[str, str]:
    try:
        async with repo._ext() as session:  # noqa: SLF001
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"db error: {exc!s}")
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}
