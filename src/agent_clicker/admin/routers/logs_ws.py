"""WebSocket log streaming."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from agent_clicker.observability.broadcaster import LogBroadcaster

router = APIRouter(tags=["logs"])
logger = logging.getLogger(__name__)

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


def _passes(record: dict, level: str | None, task_id: int | None, worker_id: str | None) -> bool:
    if level:
        min_level = _LEVELS.get(level.upper(), 0)
        rec_level = _LEVELS.get(str(record.get("level", "")).upper(), 0)
        if rec_level < min_level:
            return False
    if task_id is not None and record.get("task_id") != task_id:
        return False
    if worker_id and record.get("worker_id") != worker_id:
        return False
    return True


@router.websocket("/ws/logs")
async def ws_logs(
    ws: WebSocket,
    level: str | None = Query(default=None),
    task_id: int | None = Query(default=None),
    worker_id: str | None = Query(default=None),
) -> None:
    await ws.accept()
    broadcaster: LogBroadcaster = ws.app.state.broadcaster
    # send snapshot first
    try:
        for rec in broadcaster.snapshot():
            if _passes(rec, level, task_id, worker_id):
                await ws.send_json(rec)
    except WebSocketDisconnect:
        return
    # stream
    try:
        async for rec in broadcaster.subscribe():
            if _passes(rec, level, task_id, worker_id):
                try:
                    await ws.send_json(rec)
                except WebSocketDisconnect:
                    return
    except (WebSocketDisconnect, asyncio.CancelledError):
        return
    except Exception:
        logger.exception("ws.logs.error")
        try:
            await ws.close(code=1011)
        except Exception:
            pass
