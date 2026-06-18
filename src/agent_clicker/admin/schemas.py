"""Pydantic schemas used by Admin REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from agent_clicker.domain.task import AdProxyConfigDTO, TaskDTO

T = TypeVar("T")


class TaskOut(BaseModel):
    id: int
    ad_id: int
    status: str
    description: str
    link: str
    created_at: datetime | None
    exec_time: datetime | None
    attempts: int
    max_attempts: int
    last_error: str | None
    worker_id: str | None
    locked_at: datetime | None
    profile: dict[str, Any] | None
    result: dict[str, Any] | None
    cookies_count: int = 0

    @classmethod
    def from_dto(cls, dto: TaskDTO) -> TaskOut:
        return cls(
            id=dto.id,
            ad_id=dto.ad_id,
            status=dto.status,
            description=dto.description,
            link=dto.link,
            created_at=dto.created_at,
            exec_time=dto.exec_time,
            attempts=dto.attempts,
            max_attempts=dto.max_attempts,
            last_error=dto.last_error,
            worker_id=dto.worker_id,
            locked_at=dto.locked_at,
            profile=dto.profile,
            result=dto.result,
            cookies_count=len(dto.cookies) if dto.cookies else 0,
        )


class PageOut(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class CreateTaskRequest(BaseModel):
    ad_id: int
    link: str
    description: str
    exec_time: datetime | None = None
    max_attempts: int | None = None
    # Optional: cookie header string ("k=v; k2=v2") or pre-parsed Playwright cookies.
    cookies: str | list[dict[str, Any]] | None = None
    # Manual HTTP-proxy override (domain/IP, port, login, password)
    proxy_host: str | None = None
    proxy_port: int | None = None
    proxy_login: str | None = None
    proxy_password: str | None = None


class AdProxyConfigOut(BaseModel):
    ad_id: int
    proxy_host: str
    proxy_port: int
    proxy_login: str | None = None
    proxy_password: str | None = None

    @classmethod
    def from_dto(cls, dto: AdProxyConfigDTO) -> AdProxyConfigOut:
        return cls(
            ad_id=dto.ad_id,
            proxy_host=dto.proxy_host,
            proxy_port=dto.proxy_port,
            proxy_login=dto.proxy_login,
            proxy_password=dto.proxy_password,
        )


class AdProxyConfigUpsert(BaseModel):
    ad_id: int
    proxy_host: str
    proxy_port: int
    proxy_login: str | None = None
    proxy_password: str | None = None
