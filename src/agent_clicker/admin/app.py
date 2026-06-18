"""FastAPI app factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from agent_clicker.admin.routers import ad_proxy, artifacts, health, logs_ws, tasks
from agent_clicker.admin.routers import settings as settings_router
from agent_clicker.config import Settings
from agent_clicker.db.repository import AdProxyRepository, TaskRepository
from agent_clicker.observability.artifacts import ArtifactStore
from agent_clicker.observability.broadcaster import LogBroadcaster
from agent_clicker.settings_store import SettingsStore

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    *,
    repo: TaskRepository,
    ad_proxy_repo: AdProxyRepository,
    settings_store: SettingsStore,
    broadcaster: LogBroadcaster,
    artifact_store: ArtifactStore,
    static_settings: Settings,
) -> FastAPI:
    app = FastAPI(title="agent-clicker admin", version="0.1.0")
    app.state.task_repo = repo
    app.state.ad_proxy_repo = ad_proxy_repo
    app.state.settings_store = settings_store
    app.state.broadcaster = broadcaster
    app.state.artifact_store = artifact_store
    app.state.static_settings = static_settings

    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(ad_proxy.router)
    app.include_router(settings_router.router)
    app.include_router(artifacts.router)
    app.include_router(logs_ws.router)

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )

    def render(name: str) -> str:
        return env.get_template(name).render(
            enable_task_mutations=static_settings.enable_task_mutations
        )

    @app.get("/", response_class=HTMLResponse)
    async def page_tasks() -> str:
        return render("tasks.html")

    @app.get("/ad-proxy", response_class=HTMLResponse)
    async def page_ad_proxy() -> str:
        return render("ad_proxy.html")

    @app.get("/settings", response_class=HTMLResponse)
    async def page_settings() -> str:
        return render("settings.html")

    @app.get("/logs", response_class=HTMLResponse)
    async def page_logs() -> str:
        return render("logs.html")

    return app
