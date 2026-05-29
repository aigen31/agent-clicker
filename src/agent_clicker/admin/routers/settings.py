"""Settings REST router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from agent_clicker.admin.dependencies import get_settings_store
from agent_clicker.config import AgentSettings, BrowserProfileDefaults, WorkerRuntimeSettings
from agent_clicker.settings_store import SettingsStore

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/agent", response_model=AgentSettings)
async def get_agent(store: SettingsStore = Depends(get_settings_store)) -> AgentSettings:
    return await store.get_agent()


@router.put("/agent", response_model=AgentSettings)
async def put_agent(
    new: AgentSettings, store: SettingsStore = Depends(get_settings_store)
) -> AgentSettings:
    await store.update_agent(new)
    return await store.get_agent()


@router.get("/browser", response_model=BrowserProfileDefaults)
async def get_browser(store: SettingsStore = Depends(get_settings_store)) -> BrowserProfileDefaults:
    return await store.get_browser()


@router.put("/browser", response_model=BrowserProfileDefaults)
async def put_browser(
    new: BrowserProfileDefaults, store: SettingsStore = Depends(get_settings_store)
) -> BrowserProfileDefaults:
    await store.update_browser(new)
    return await store.get_browser()


@router.get("/worker", response_model=WorkerRuntimeSettings)
async def get_worker(store: SettingsStore = Depends(get_settings_store)) -> WorkerRuntimeSettings:
    return await store.get_worker()


@router.put("/worker", response_model=WorkerRuntimeSettings)
async def put_worker(
    new: WorkerRuntimeSettings, store: SettingsStore = Depends(get_settings_store)
) -> WorkerRuntimeSettings:
    await store.update_worker(new)
    return await store.get_worker()
