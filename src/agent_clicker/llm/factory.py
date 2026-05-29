"""LLM factory — builds langchain ChatOpenAI used by browser-use."""

from __future__ import annotations

from typing import Any

from agent_clicker.config import AgentSettings, Settings


def build_llm(agent: AgentSettings, static: Settings) -> Any:
    """Build the LLM accepted by browser-use Agent.

    browser-use ships its own OpenAI-compatible wrapper (`browser_use.llm.ChatOpenAI`)
    that exposes the `.provider` attribute the Agent relies on. We prefer it; fall
    back to langchain's `ChatOpenAI` only if browser_use isn't installed (tests).
    """
    try:
        from browser_use.llm import ChatOpenAI as _BUChat  # type: ignore

        return _BUChat(
            model=agent.llm_model,
            api_key=static.llm_api_key.get_secret_value(),
            base_url=static.llm_base_url or None,
            temperature=0.7,
        )
    except Exception:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=agent.llm_model,
            api_key=static.llm_api_key.get_secret_value(),
            base_url=static.llm_base_url or None,
            temperature=0.7,
        )
