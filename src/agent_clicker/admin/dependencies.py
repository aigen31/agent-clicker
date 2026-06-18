"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import HTTPException, Request

from agent_clicker.config import Settings
from agent_clicker.db.repository import AdProxyRepository, TaskRepository
from agent_clicker.observability.artifacts import ArtifactStore
from agent_clicker.observability.broadcaster import LogBroadcaster
from agent_clicker.settings_store import SettingsStore


def get_task_repo(request: Request) -> TaskRepository:
    return request.app.state.task_repo


def get_ad_proxy_repo(request: Request) -> AdProxyRepository:
    return request.app.state.ad_proxy_repo


def get_settings_store(request: Request) -> SettingsStore:
    return request.app.state.settings_store


def get_broadcaster(request: Request) -> LogBroadcaster:
    return request.app.state.broadcaster


def get_artifact_store(request: Request) -> ArtifactStore:
    return request.app.state.artifact_store


def get_static_settings(request: Request) -> Settings:
    return request.app.state.static_settings


def require_mutations(request: Request) -> None:
    settings: Settings = request.app.state.static_settings
    if not settings.enable_task_mutations:
        raise HTTPException(status_code=403, detail="task mutations disabled in this environment")
