from __future__ import annotations

from pathlib import Path

from forgecode.agent import AgentLoop
from forgecode.schemas import AgentConfig, ModelResponse, StopReason, ToolCall


class ScriptedModel:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[list[dict], list[dict]]] = []

    def complete(self, messages, tools):
        self.calls.append((list(messages), list(tools)))
        if not self.responses:
            raise AssertionError("ScriptedModel ran out of responses")
        return self.responses.pop(0)


def final(text: str) -> ModelResponse:
    return ModelResponse(content=text, raw_message={"role": "assistant", "content": text})


def call_tool(call_id: str, name: str, arguments: dict) -> ModelResponse:
    return ModelResponse(
        content=None,
        tool_calls=(ToolCall(id=call_id, name=name, arguments=arguments),),
    )


def test_loop_executes_tool_then_feeds_observation_back(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text("print('hello')\n", encoding="utf-8")
    model = ScriptedModel(
        [
            call_tool("call-1", "read_file", {"path": "hello.py"}),
            final("hello.py prints hello"),
        ]
    )
    agent = AgentLoop.for_workspace(model, tmp_path)

    result = agent.run("Explain hello.py")

    assert result.stop_reason is StopReason.COMPLETED
    assert result.final_text == "hello.py prints hello"
    assert result.stats.steps == 2
    assert result.stats.model_calls == 2
    assert result.stats.tool_calls == 1
    assert result.messages[-1]["role"] == "assistant"
    tool_message = result.messages[-2]
    assert tool_message["role"] == "tool"
    assert "1: print('hello')" in tool_message["content"]
    assert {tool["function"]["name"] for tool in model.calls[0][1]} == {
        "list_files",
        "read_file",
        "search_text",
        "run_command",
    }


def test_unknown_tool_is_returned_as_an_observation(tmp_path: Path) -> None:
    model = ScriptedModel(
        [
            call_tool("call-unknown", "does_not_exist", {}),
            final("I could not use that tool."),
        ]
    )
    result = AgentLoop.for_workspace(model, tmp_path).run("Try it")

    assert result.stop_reason is StopReason.COMPLETED
    assert result.stats.tool_errors == 1
    assert "Unknown tool" in result.messages[-2]["content"]


def test_loop_stops_at_step_limit(tmp_path: Path) -> None:
    model = ScriptedModel([call_tool(f"call-{i}", "list_files", {}) for i in range(5)])
    agent = AgentLoop.for_workspace(model, tmp_path, AgentConfig(max_steps=2))

    result = agent.run("Keep exploring")

    assert result.stop_reason is StopReason.STEP_LIMIT
    assert result.stats.steps == 2
    assert result.stats.model_calls == 2
    assert result.error == "Agent reached max_steps=2"
