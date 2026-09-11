"""Model interfaces and the optional OpenAI Chat Completions adapter."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, Sequence

from .schemas import Message, ModelResponse, ToolCall


class ChatModel(Protocol):
    """The one capability the agent loop needs from a model."""

    def complete(self, messages: Sequence[Message], tools: Sequence[dict]) -> ModelResponse:
        """Return the next assistant response for the current conversation."""


class OpenAIChatModel:
    """Thin adapter around OpenAI-compatible Chat Completions APIs.

    The import is delayed until construction so tests can inspect the adapter
    without creating a network client.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on local setup
            raise RuntimeError(
                "The OpenAI adapter requires the 'openai' package. "
                "Install the project dependencies first."
            ) from exc

        resolved_key = _resolve_api_key(api_key)
        if not resolved_key:
            raise RuntimeError(
                "API key is not set. Set FORGECODE_API_KEY or OPENAI_API_KEY."
            )

        self.model = model or os.environ.get("FORGECODE_MODEL", "gpt-4o-mini")
        resolved_base_url = _resolve_base_url(base_url)
        client_kwargs: dict[str, Any] = {"api_key": resolved_key}
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url
        self._client = OpenAI(**client_kwargs)

    def complete(self, messages: Sequence[Message], tools: Sequence[dict]) -> ModelResponse:
        """调用模型一次，并把 SDK 响应转换为 ``ModelResponse``。"""

        response = self._client.chat.completions.create(
            model=self.model,
            messages=list(messages),
            tools=list(tools),
        )
        message = response.choices[0].message
        raw_message = message.model_dump(exclude_none=True)
        parsed_calls: list[ToolCall] = []

        for raw_call in message.tool_calls or []:
            arguments = _parse_arguments(raw_call.function.arguments)
            parsed_calls.append(
                ToolCall(
                    id=raw_call.id,
                    name=raw_call.function.name,
                    arguments=arguments,
                )
            )

        return ModelResponse(
            content=message.content,
            tool_calls=tuple(parsed_calls),
            raw_message=raw_message,
        )


def _parse_arguments(raw_arguments: str | dict) -> dict:
    """Parse a provider's JSON arguments and surface useful errors."""

    if isinstance(raw_arguments, dict):
        return raw_arguments
    try:
        parsed = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned invalid tool arguments: {raw_arguments!r}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must be a JSON object")
    return parsed


def _resolve_api_key(explicit: str | None) -> str | None:
    """Resolve an API key, preferring explicit input over environment values."""

    return (
        explicit
        or os.environ.get("FORGECODE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )


def _resolve_base_url(explicit: str | None) -> str | None:
    """Resolve an OpenAI-compatible endpoint from explicit input or environment."""

    return (
        explicit
        or os.environ.get("FORGECODE_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_API_BASE")
    )


class LangChainChatModel(Protocol):
    """Minimal V1 model surface: bind tools, then invoke messages."""

    def bind_tools(self, tools: Sequence[Any]) -> Any:
        """Return a runnable model configured with the supplied tools."""


def create_langchain_chat_model(
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LangChainChatModel:
    """Create a LangChain ChatOpenAI model from explicit values or environment.

    langchain-openai is imported lazily. This keeps unit tests independent
    from provider packages while still giving the CLI a standard production
    adapter.
    """

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - depends on local setup
        raise RuntimeError(
            "The LangChain adapter requires 'langchain-openai'. "
            "Install the project dependencies first."
        ) from exc

    resolved_key = _resolve_api_key(api_key)
    if not resolved_key:
        raise RuntimeError(
            "API key is not set. Set FORGECODE_API_KEY or OPENAI_API_KEY."
        )

    model_name = model or os.environ.get("FORGECODE_MODEL", "gpt-4o-mini")
    resolved_base_url = _resolve_base_url(base_url)
    kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": resolved_key,
    }
    if resolved_base_url:
        kwargs["base_url"] = resolved_base_url
    return ChatOpenAI(**kwargs)
