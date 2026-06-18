"""LLM factory — builds ChatOpenAI used by browser-use.

Supports OpenAI and non-OpenAI providers (DeepSeek, etc.).
For non-OpenAI providers:
1. Does NOT send ``response_format`` (DeepSeek rejects it).
2. Embeds the JSON schema in the system prompt instead.
3. Strips markdown code fences (`` ```json … ``` ``) that
   DeepSeek wraps around its JSON responses.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agent_clicker.config import AgentSettings, Settings

_MD_JSON_FENCE_RE = re.compile(
    r"^```(?:json)?\s*\n(.*?)\n```\s*$",
    re.DOTALL | re.MULTILINE,
)


def _strip_md_fence(text: str) -> str:
    """Remove markdown JSON code fences from a string.

    DeepSeek wraps JSON responses in ```json … ``` fences even when
    asked to output raw JSON.  browser-use's ``model_validate_json``
    cannot parse those, so we strip them first.
    """
    m = _MD_JSON_FENCE_RE.match(text)
    return m.group(1) if m else text


def build_llm(agent: AgentSettings, static: Settings) -> Any:
    """Build the LLM accepted by browser-use Agent.

    Uses browser-use's own ``ChatOpenAI`` wrapper when available.
    For non-OpenAI providers (detected from ``base_url``), passes
    ``dont_force_structured_output=True`` and
    ``add_schema_to_system_prompt=True``, and wraps ``ainvoke`` to
    strip markdown code fences from the response.
    """
    try:
        from browser_use.llm import ChatOpenAI as _BUChat  # type: ignore
    except Exception:
        from langchain_openai import ChatOpenAI  # type: ignore

        return ChatOpenAI(
            model=agent.llm_model,
            api_key=static.llm_api_key.get_secret_value(),
            base_url=static.llm_base_url or None,
            temperature=0.7,
        )

    base_url = (static.llm_base_url or "").lower()
    is_openai = "api.openai.com" in base_url or not base_url

    if is_openai:
        # OpenAI — use as-is.
        return _BUChat(
            model=agent.llm_model,
            api_key=static.llm_api_key.get_secret_value(),
            base_url=static.llm_base_url or None,
            temperature=0.7,
        )

    # Non-OpenAI provider (DeepSeek, etc.) — wrap with compat fixes.
    from browser_use.llm.exceptions import ModelProviderError  # type: ignore
    from browser_use.llm.openai.serializer import OpenAIMessageSerializer  # type: ignore
    from browser_use.llm.views import ChatInvokeCompletion  # type: ignore

    llm = _BUChat(
        model=agent.llm_model,
        api_key=static.llm_api_key.get_secret_value(),
        base_url=static.llm_base_url or None,
        temperature=0.7,
        # Skip ``response_format`` — non-OpenAI providers reject it.
        dont_force_structured_output=True,
        add_schema_to_system_prompt=True,
    )

    original_ainvoke = llm.ainvoke

    async def _patched_ainvoke(
        messages: Any,
        output_format: type[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Wrap ``ainvoke`` to strip markdown fences from the response."""
        # Serialize and inject schema ourselves (same as parent).
        openai_messages = OpenAIMessageSerializer.serialize_messages(messages)

        model_params: dict[str, Any] = {}
        if llm.temperature is not None:
            model_params["temperature"] = llm.temperature
        if llm.frequency_penalty is not None:
            model_params["frequency_penalty"] = llm.frequency_penalty
        if llm.max_completion_tokens is not None:
            model_params["max_completion_tokens"] = llm.max_completion_tokens
        if llm.top_p is not None:
            model_params["top_p"] = llm.top_p
        if llm.seed is not None:
            model_params["seed"] = llm.seed
        if llm.service_tier is not None:
            model_params["service_tier"] = llm.service_tier

        # Inject schema into system prompt to guide the model
        # without relying on ``response_format``.
        if output_format is not None:
            schema = output_format.model_json_schema()
            schema_text = (
                "\n\nRespond ONLY with valid JSON matching this schema.\n"
                + json.dumps(schema, indent=2)
                + "\nDO NOT wrap the JSON in markdown code fences."
            )
            if openai_messages and openai_messages[0].get("role") == "system":
                if isinstance(openai_messages[0]["content"], str):
                    openai_messages[0]["content"] += schema_text

        # Make the API call WITHOUT ``response_format``.
        try:
            response = await llm.get_client().chat.completions.create(
                model=llm.model,
                messages=openai_messages,
                **model_params,
            )
        except Exception as e:
            raise ModelProviderError(message=str(e), model=llm.name) from e

        choice = response.choices[0] if response.choices else None
        if choice is None:
            raise ModelProviderError(
                message="Invalid response: missing choices",
                model=llm.name,
            )

        raw = (choice.message.content or "").strip()

        if output_format is not None:
            # Strip markdown fences before parsing.
            raw = _strip_md_fence(raw)
            try:
                parsed = output_format.model_validate_json(raw)
            except Exception as e:
                raise ModelProviderError(
                    message=f"Failed to parse structured output: {e}",
                    model=llm.name,
                ) from e

            return ChatInvokeCompletion(
                completion=parsed,
                usage=llm._get_usage(response),
                stop_reason=choice.finish_reason,
            )

        return ChatInvokeCompletion(
            completion=raw,
            usage=llm._get_usage(response),
            stop_reason=choice.finish_reason,
        )

    llm.ainvoke = _patched_ainvoke  # type: ignore[method-assign]
    return llm
