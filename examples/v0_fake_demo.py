"""Run a deterministic V0 demo without an API key.

Usage from the repository root:

    python examples/v0_fake_demo.py
"""

from __future__ import annotations

from pathlib import Path

from forgecode.agent import AgentLoop
from forgecode.schemas import ModelResponse, ToolCall


class DemoModel:
    """A tiny scripted model that makes the Agent Loop visible."""

    def __init__(self) -> None:
        self.step = 0

    def complete(self, messages, tools) -> ModelResponse:
        self.step += 1
        if self.step == 1:
            return ModelResponse(
                content=None,
                tool_calls=(ToolCall("demo-1", "list_files", {"max_entries": 20}),),
            )
        if self.step == 2:
            return ModelResponse(
                content=None,
                tool_calls=(ToolCall("demo-2", "read_file", {"path": "README.md"}),),
            )
        return ModelResponse(
            content="我浏览了仓库，并读取了 README.md。V0 的循环已经完成。",
            raw_message={
                "role": "assistant",
                "content": "我浏览了仓库，并读取了 README.md。V0 的循环已经完成。",
            },
        )


def main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    result = AgentLoop.for_workspace(DemoModel(), workspace).run(
        "浏览仓库并读取 README.md，然后告诉我你做了什么。"
    )

    for index, message in enumerate(result.messages):
        print(f"\n--- message {index} ({message['role']}) ---")
        print(message.get("content") or message.get("tool_calls"))
    print(
        f"\nstop_reason={result.stop_reason.value} "
        f"steps={result.stats.steps} tool_calls={result.stats.tool_calls}"
    )


if __name__ == "__main__":
    main()
