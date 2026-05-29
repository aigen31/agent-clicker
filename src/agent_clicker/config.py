"""Static and dynamic configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Immutable env-only settings (loaded once at startup)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Databases
    external_tasks_dsn: str = Field(
        default="postgresql+asyncpg://agent:agent@localhost:5432/agent_clicker",
    )
    internal_state_dsn: str = Field(
        default="postgresql+asyncpg://agent:agent@localhost:5432/agent_clicker",
    )

    # LLM
    llm_api_key: SecretStr = SecretStr("sk-changeme")
    llm_base_url: str = "https://api.openai.com/v1"

    # Proxy
    proxy_provider_url: str = ""
    proxy_provider_token: SecretStr = SecretStr("")
    proxy_list: str = ""  # CSV: "server|user|pass|geo,server|..."

    # Infra
    artifacts_dir: str = "./artifacts"
    log_level: str = "INFO"
    log_buffer_size: int = 2000

    # Admin
    admin_host: str = "127.0.0.1"
    admin_port: int = 8080
    admin_allow_public: bool = False
    enable_task_mutations: bool = True  # dev only

    # Boot defaults (copied into settings table on first run)
    boot_worker_concurrency: int = 2
    boot_lease_timeout_seconds: int = 600
    boot_max_attempts: int = 3
    boot_backoff_base_seconds: int = 30
    boot_min_time_on_site_seconds: int = 30
    boot_max_time_on_site_seconds: int = 180

    boot_llm_model: str = "gpt-4o-mini"
    boot_agent_max_steps: int = 50
    boot_agent_use_vision: bool = True
    boot_agent_use_thinking: bool = True
    boot_agent_max_failures: int = 5
    boot_agent_step_timeout: int = 180
    boot_agent_max_actions_per_step: int = 10
    boot_agent_enable_planning: bool = True
    boot_agent_extend_system_message: str = ""

    boot_browser_headless: bool = True
    boot_browser_disable_security: bool = False
    boot_browser_wait_between_actions: float = 0.5
    boot_browser_minimum_wait_page_load_time: float = 0.5
    boot_browser_wait_for_network_idle_page_load_time: float = 1.0
    boot_browser_highlight_elements: bool = False
    boot_browser_enable_default_extensions: bool = True
    boot_browser_cross_origin_iframes: bool = False
    boot_browser_max_iframes: int = 10


class AgentSettings(BaseModel):
    llm_model: str = "gpt-4o-mini"
    max_steps: int = 50
    use_vision: bool = True
    use_thinking: bool = True
    max_failures: int = 5
    step_timeout: int = 180
    max_actions_per_step: int = 10
    enable_planning: bool = True
    extend_system_message: str = ""


class BrowserProfileDefaults(BaseModel):
    headless: bool = True
    disable_security: bool = False
    wait_between_actions: float = 0.5
    minimum_wait_page_load_time: float = 0.5
    wait_for_network_idle_page_load_time: float = 1.0
    highlight_elements: bool = False
    enable_default_extensions: bool = True
    cross_origin_iframes: bool = False
    max_iframes: int = 10


class WorkerRuntimeSettings(BaseModel):
    worker_concurrency: int = 2
    lease_timeout_seconds: int = 600
    max_attempts: int = 3
    backoff_base_seconds: int = 30
    min_time_on_site_seconds: int = 30
    max_time_on_site_seconds: int = 180


SettingsKey = Literal["agent", "browser", "worker"]
