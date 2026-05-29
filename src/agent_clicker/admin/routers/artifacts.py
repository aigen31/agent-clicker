"""Artifacts router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from agent_clicker.admin.dependencies import get_artifact_store
from agent_clicker.observability.artifacts import ArtifactFile, ArtifactStore

router = APIRouter(prefix="/api/tasks", tags=["artifacts"])


@router.get("/{task_id}/artifacts", response_model=list[ArtifactFile])
async def list_artifacts(
    task_id: int, store: ArtifactStore = Depends(get_artifact_store)
) -> list[ArtifactFile]:
    return store.list_for(task_id)


@router.get("/{task_id}/artifacts/{filename}")
async def get_artifact(
    task_id: int, filename: str, store: ArtifactStore = Depends(get_artifact_store)
) -> FileResponse:
    try:
        path = store.resolve_safe(task_id, filename)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return FileResponse(path)
