"""Domain DTOs for tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


class TaskStatus:
    """Status string constants (no Enum — production DB uses VARCHAR without check constraint)."""

    PENDING = "created"  # external schema uses 'created' as the initial pending state
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"

    LEASABLE: tuple[str, ...] = (PENDING, SCHEDULED)
    TERMINAL: tuple[str, ...] = (DONE, FAILED, SKIPPED)
    ALL: tuple[str, ...] = (PENDING, SCHEDULED, IN_PROGRESS, DONE, FAILED, SKIPPED)


@dataclass(frozen=True, slots=True)
class TaskDTO:
    id: int
    ad_id: int
    status: str
    description: str
    link: str
    created_at: datetime
    exec_time: datetime | None
    # internal runtime (None if no runtime row yet)
    attempts: int = 0
    max_attempts: int = 3
    last_error: str | None = None
    worker_id: str | None = None
    locked_at: datetime | None = None
    profile: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class TaskFilters(BaseModel):
    status: str | None = None
    ad_id: int | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class TaskResult:
    is_successful: bool
    steps: int
    duration_seconds: float
    final_result: str | None
    artifacts_dir: str | None
    error: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "is_successful": self.is_successful,
            "steps": self.steps,
            "duration_seconds": self.duration_seconds,
            "final_result": self.final_result,
            "artifacts_dir": self.artifacts_dir,
            "error": self.error,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            **self.extra,
        }
