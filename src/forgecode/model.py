"""Model interfaces and the optional OpenAI Chat Completions adapter."""

from __future__ import annotations

import json
import os
from typing import Protocol, Sequence

from .schemas import Message, ModelResponse, ToolCall


class ChatModel(Protocol):
    """The one capability the agent loop needs from a model."""

    def complete(self, messages: Sequence[Message], tools: Sequence[dict]) -> ModelResponse:
        """Return the next assistant response for the current conversation."""


class OpenAIChatModel:
    """Thin adapter around OpenAI-compatible Chat Completions APIs.

    The import is delayed until construction so unit tests can use a Fake Model
    without installing or configuring an API client.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on local setup
            raise RuntimeError(
                "The OpenAI adapter requires the 'openai' package. "
                "Install the project dependencies first."
            ) from exc

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.model = model or os.environ.get("FORGECODE_MODEL", "gpt-4o-mini")
        self._client = OpenAI(api_key=resolved_key)

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
