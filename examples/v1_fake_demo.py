"""Run the V1 loop with a deterministic fake LangChain model.

The demo exercises the same tool-call protocol as a real chat model, but it
never sends a request over the network. It is useful when learning the loop or
checking a fresh installation without an API key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from forgecode.agent import CodingAgent
from forgecode.schemas import StopReason


class ScriptedModel:
    """A tiny fake model implementing bind_tools and invoke."""

    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = list(responses)
        self.bound_tools: list[Any] = []

    def bind_tools(self, tools: list[Any]) -> "ScriptedModel":
        self.bound_tools = list(tools)
        return self

    def invoke(self, messages: list[Any]) -> AIMessage:
        del messages
        if not self.responses:
            raise AssertionError("ScriptedModel ran out of responses")
        return self.responses.pop(0)


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


def main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    target = workspace / "examples" / "v1_demo_target.txt"
    original = target.read_text(encoding="utf-8")
    patch = """\
diff --git a/examples/v1_demo_target.txt b/examples/v1_demo_target.txt
--- a/examples/v1_demo_target.txt
+++ b/examples/v1_demo_target.txt
@@ -1 +1 @@
-This file is a tracked fixture for the ForgeCode V1 fake demo.
+This line was changed by the ForgeCode V1 fake demo.
"""

    model = ScriptedModel(
        [
            tool_call("call-1", "list_files", {"path": "examples"}),
            tool_call(
                "call-2",
                "read_file",
                {"path": "README.md", "start_line": 1, "end_line": 8},
            ),
            tool_call("call-3", "apply_patch", {"patch": patch}),
            tool_call("call-4", "git_diff", {"path": "examples/v1_demo_target.txt"}),
            tool_call("call-5", "read_file", {"path": "examples/v1_demo_target.txt"}),
            AIMessage(content="I inspected the repository, applied the patch, and verified the change."),
        ]
    )

    try:
        result = CodingAgent.for_workspace(model, workspace).run(
            "Inspect the repository, update the demo fixture, and verify the diff."
        )
        print(result.final_text)
        print(
            f"[stop_reason={result.stop_reason.value} steps={result.stats.steps} "
            f"model_calls={result.stats.model_calls} tool_calls={result.stats.tool_calls} "
            f"tool_errors={result.stats.tool_errors}]"
        )
        if result.stop_reason is not StopReason.COMPLETED:
            raise SystemExit(result.error or "V1 demo did not complete")
    finally:
        # The demo is repeatable: restore the tracked fixture after the run.
        target.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    main()
