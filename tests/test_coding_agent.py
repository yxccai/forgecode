from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from forgecode.agent import CodingAgent
from forgecode.schemas import AgentConfig, StopReason


class ScriptedModel:
    """Deterministic LangChain test model that returns a fixed AIMessage sequence."""

    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = list(responses)
        self.bind_calls = 0
        self.bound_tools: list[Any] = []
        self.invoke_messages: list[list[Any]] = []
        self.stream_calls = 0

    def bind_tools(self, tools: list[Any]) -> "ScriptedModel":
        self.bind_calls += 1
        self.bound_tools = list(tools)
        return self

    def invoke(self, messages: list[Any]) -> AIMessage:
        self.invoke_messages.append(list(messages))
        if not self.responses:
            raise AssertionError("ScriptedModel ran out of responses")
        return self.responses.pop(0)

    def stream(self, messages: list[Any]) -> Any:
        self.stream_calls += 1
        self.invoke_messages.append(list(messages))
        if not self.responses:
            raise AssertionError("ScriptedModel ran out of responses")

        response = self.responses.pop(0)
        text = str(response.content or "")
        midpoint = max(1, len(text) // 2)
        yield AIMessageChunk(content=text[:midpoint])
        yield AIMessageChunk(content=text[midpoint:])


def tool_call(call_id: str, name: str, args: dict[str, Any]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": call_id,
                "name": name,
                "args": args,
                "type": "tool_call",
            }
        ],
    )


def final(text: str) -> AIMessage:
    return AIMessage(content=text)


def test_agent_executes_tool_and_returns_final_message(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text("print('hello')\n", encoding="utf-8")
    model = ScriptedModel(
        [
            tool_call("call-1", "read_file", {"path": "hello.py"}),
            final("hello.py prints hello"),
        ]
    )

    result = CodingAgent.for_workspace(model, tmp_path).run("Explain hello.py")

    assert result.stop_reason is StopReason.COMPLETED
    assert result.final_text == "hello.py prints hello"
    assert result.stats.steps == 2
    assert result.stats.model_calls == 2
    assert result.stats.tool_calls == 1
    assert result.stats.tool_errors == 0
    assert isinstance(result.messages[-1], AIMessage)
    assert isinstance(result.messages[-2], ToolMessage)
    assert "print('hello')" in result.messages[-2].content
    assert model.bind_calls == 1
    assert {tool.name for tool in model.bound_tools} == {
        "list_files",
        "read_file",
        "search_text",
        "run_command",
        "apply_patch",
        "git_diff",
    }


def test_agent_continues_existing_history(tmp_path: Path) -> None:
    model = ScriptedModel(
        [
            final("first answer"),
            final("second answer"),
        ]
    )
    agent = CodingAgent.for_workspace(model, tmp_path)

    first = agent.run("first question")
    second = agent.run("follow-up question", history=first.messages)

    assert first.final_text == "first answer"
    assert second.final_text == "second answer"
    assert len(second.messages) == 5
    assert isinstance(second.messages[-2], HumanMessage)
    assert second.messages[-2].content == "follow-up question"
    assert second.messages[2].content == "first answer"


def test_agent_streams_text_chunks(tmp_path: Path) -> None:
    model = ScriptedModel([final("streamed answer")])
    chunks: list[str] = []

    result = CodingAgent.for_workspace(model, tmp_path).run(
        "Stream the answer",
        on_text=chunks.append,
    )

    assert result.stop_reason is StopReason.COMPLETED
    assert result.final_text == "streamed answer"
    assert "".join(chunks) == "streamed answer"
    assert model.stream_calls == 1


def test_tool_error_is_returned_to_model_as_observation(tmp_path: Path) -> None:
    model = ScriptedModel(
        [
            tool_call("call-missing", "read_file", {"path": "missing.py"}),
            final("The file does not exist."),
        ]
    )

    result = CodingAgent.for_workspace(model, tmp_path).run("Read missing.py")

    assert result.stop_reason is StopReason.COMPLETED
    assert result.stats.tool_errors == 1
    tool_message = result.messages[-2]
    assert isinstance(tool_message, ToolMessage)
    assert '"ok": false' in tool_message.content
    assert "missing.py" in tool_message.content


def test_agent_stops_at_configured_step_limit(tmp_path: Path) -> None:
    model = ScriptedModel(
        [
            tool_call(f"call-{index}", "list_files", {})
            for index in range(4)
        ]
    )

    result = CodingAgent.for_workspace(
        model,
        tmp_path,
        AgentConfig(max_steps=2),
    ).run("Keep exploring")

    assert result.stop_reason is StopReason.STEP_LIMIT
    assert result.stats.steps == 2
    assert result.stats.model_calls == 2
    assert result.stats.tool_calls == 2
    assert result.error == "Agent reached max_steps=2"
