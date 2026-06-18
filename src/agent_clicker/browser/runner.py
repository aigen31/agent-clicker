"""AgentRunner: composes browser-use Agent and runs a single task."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from agent_clicker.browser.callbacks import DoneCallback, StepStreamCallback
from agent_clicker.config import Settings
from agent_clicker.domain.task import TaskDTO
from agent_clicker.llm.factory import build_llm
from agent_clicker.observability.artifacts import ArtifactStore
from agent_clicker.settings_store import SettingsStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    is_successful: bool
    steps: int
    duration_seconds: float
    final_result: str | None
    artifacts_dir: str
    history_summary: dict[str, Any]
    started_at: datetime
    finished_at: datetime


class AgentBuilder(Protocol):
    """Hook used in tests to inject a fake Agent."""

    def __call__(self, **kwargs: Any) -> Any: ...


def _default_agent_builder(**kwargs: Any) -> Any:
    from browser_use import Agent  # type: ignore

    return Agent(**kwargs)


class AgentRunner:
    def __init__(
        self,
        settings_store: SettingsStore,
        artifact_store: ArtifactStore,
        static: Settings,
        agent_builder: AgentBuilder | None = None,
    ) -> None:
        self._store = settings_store
        self._artifacts = artifact_store
        self._static = static
        self._agent_builder = agent_builder or _default_agent_builder

    async def run(
        self,
        *,
        task: TaskDTO,
        worker_id: str,
        browser_profile: Any,
    ) -> AgentRunResult:
        agent_cfg = await self._store.get_agent()
        worker_cfg = await self._store.get_worker()

        description = (task.description or "").strip()
        task_text = (
            f"Перейди на {task.link} и выполни: {description}"
            if description
            else (
                f"Перейди на {task.link} и выполни следующие действия: "
                "изучи сайт, ознакомься с его содержанием, структурой и функционалом. "
                "Прокрути несколько страниц, просмотри разделы, "
                "найди интересные материалы и взаимодействуй с контентом. "
                "Веди себя как заинтересованный посетитель."
            )
        )
        extend = (
            (agent_cfg.extend_system_message or "")
            + "\n\nВажные замечания по навигации:\n"
            "- Если ты уже залогинен (cookies переданы), не пытайся проходить логин/регистрацию.\n"
            "- Сообщения об 'ERR_TOO_MANY_REDIRECTS' и 'redirect failure' интерпретируй буквально "
            "ТОЛЬКО когда они приходят явно от браузера в виде системного сообщения об ошибке. "
            "Если страница загрузилась и видна разметка сайта (например, шапка VK, диалоги, поле "
            "ввода) — продолжай работу, не делай вывод о редиректах по одному только мнению.\n"
            "- На vk.com интерфейс на русском: диалог открывается автоматически по URL вида "
            "/im/convo/{peer_id}. Поле ввода сообщения находится снизу справа (placeholder 'Напишите сообщение'). "
            "Введи текст в это поле и нажми Enter или иконку отправки (бумажный самолётик).\n"
            "- Если действие click не сработало с 'Node with given id does not belong to the document', "
            "повтори построение карты страницы (рестарт шага) — это просто рассинхрон DOM.\n"
            "- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выполнять действие `evaluate` с JavaScript-кодом, который "
            "очищает cookies, localStorage, sessionStorage или вызывает `document.cookie = ...; expires=...`. "
            "Cookies переданы заранее и должны сохраняться. Очистка cookies немедленно ломает авторизацию "
            "и приводит к настоящим ERR_TOO_MANY_REDIRECTS. Если кажется, что 'надо обновить состояние' — "
            "просто сделай scroll/wait или повтори навигацию, но НИКОГДА не трогай cookies/storage.\n"
            "- Если ты уже совершил 2+ навигации на vk.com и страница не отображается — это твоя ошибка "
            "интерпретации, а не реальный редирект. Сделай `wait` 3 секунды и переснял DOM."
            "\n\nПосле выполнения основного действия веди себя как живой пользователь: "
            f"пробудь на сайте не менее {worker_cfg.min_time_on_site_seconds} секунд "
            f"(но не более {worker_cfg.max_time_on_site_seconds}), пролистай страницу, "
            "при наличии — перейди на 1–2 случайные внутренние ссылки и вернись."
        ).strip()

        out_dir = self._artifacts.dir_for(task.id)
        step_cb = StepStreamCallback(task.id, worker_id, logger)
        done_cb = DoneCallback(task.id, worker_id, logger)

        llm = build_llm(agent_cfg, self._static)
        agent = self._agent_builder(
            task=task_text,
            llm=llm,
            browser_profile=browser_profile,
            max_steps=agent_cfg.max_steps,
            use_vision=agent_cfg.use_vision,
            use_thinking=agent_cfg.use_thinking,
            max_failures=agent_cfg.max_failures,
            step_timeout=agent_cfg.step_timeout,
            max_actions_per_step=agent_cfg.max_actions_per_step,
            enable_planning=agent_cfg.enable_planning,
            extend_system_message=extend,
            register_new_step_callback=step_cb,
            register_done_callback=done_cb,
            output_dir=str(out_dir),
        )

        hard_timeout = min(
            agent_cfg.step_timeout * agent_cfg.max_steps,
            worker_cfg.lease_timeout_seconds - 30,
        )
        hard_timeout = max(hard_timeout, 30)

        started = datetime.utcnow()
        t0 = time.monotonic()
        try:
            history = await asyncio.wait_for(agent.run(), timeout=hard_timeout)
        finally:
            close = getattr(agent, "close", None)
            if callable(close):
                try:
                    res = close()
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
        elapsed = time.monotonic() - t0
        finished = datetime.utcnow()

        def _safe(fn: Any, default: Any = None) -> Any:
            try:
                v = fn()
                return v
            except Exception:
                return default

        success = bool(_safe(getattr(history, "is_successful", lambda: False), False))
        steps = int(_safe(getattr(history, "number_of_steps", lambda: step_cb.step_no), step_cb.step_no))
        final = _safe(getattr(history, "final_result", lambda: None), None)
        summary = {
            "history_type": type(history).__name__,
            "n_artifacts": len(list(out_dir.iterdir())) if out_dir.exists() else 0,
        }
        return AgentRunResult(
            is_successful=success,
            steps=steps,
            duration_seconds=elapsed,
            final_result=str(final) if final else None,
            artifacts_dir=str(out_dir),
            history_summary=summary,
            started_at=started,
            finished_at=finished,
        )
