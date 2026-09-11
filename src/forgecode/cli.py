"""Command-line entry point for the V1 agent."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .agent import CodingAgent
from .model import create_langchain_chat_model
from .schemas import AgentConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ForgeCode V1 repository-aware coding agent")
    parser.add_argument("task", help="Natural-language task for the agent")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Repository workspace (default: current directory)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("FORGECODE_MODEL", "gpt-4o-mini"),
        help="Model name (default: FORGECODE_MODEL or gpt-4o-mini)",
    )
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--show-trace", action="store_true", help="Print messages and tool results")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        model = create_langchain_chat_model(model=args.model)
        agent = CodingAgent.for_workspace(
            model=model,
            workspace_root=args.workspace,
            config=AgentConfig(max_steps=args.max_steps),
        )
        result = agent.run(args.task)
    except (RuntimeError, ValueError) as exc:
        print(f"ForgeCode error: {exc}")
        return 2

    if args.show_trace:
        print("--- trace ---")
        for message in result.messages:
            print(json.dumps(_message_to_dict(message), ensure_ascii=False, indent=2, default=str))
        print("--- end trace ---")

    if result.stop_reason.value == "completed":
        print(result.final_text)
        print(
            f"\n[steps={result.stats.steps} model_calls={result.stats.model_calls} "
            f"tool_calls={result.stats.tool_calls} tool_errors={result.stats.tool_errors}]"
        )
        return 0

    print(f"ForgeCode stopped: {result.stop_reason.value}")
    if result.error:
        print(result.error)
    return 1


def _message_to_dict(message: object) -> object:
    """Convert a LangChain message into readable JSON for --show-trace."""

    model_dump = getattr(message, "model_dump", None)
    if callable(model_dump):
        return model_dump(exclude_none=True)
    return {"type": type(message).__name__, "content": str(message)}
