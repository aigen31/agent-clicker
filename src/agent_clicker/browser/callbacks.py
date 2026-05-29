"""browser-use step/done callbacks → structured logs."""

from __future__ import annotations

import logging
from typing import Any


class StepStreamCallback:
    def __init__(self, task_id: int, worker_id: str, logger: logging.Logger) -> None:
        self.task_id = task_id
        self.worker_id = worker_id
        self.logger = logger
        self.step_no = 0

    async def __call__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - browser_use API
        self.step_no += 1
        self.logger.info(
            "agent.step",
            extra={"step_no": self.step_no},
        )


class DoneCallback:
    def __init__(self, task_id: int, worker_id: str, logger: logging.Logger) -> None:
        self.task_id = task_id
        self.worker_id = worker_id
        self.logger = logger

    async def __call__(self, history: Any) -> None:  # pragma: no cover - browser_use API
        try:
            success = bool(history.is_successful())
        except Exception:
            success = False
        self.logger.info("agent.done", extra={"success": success})
