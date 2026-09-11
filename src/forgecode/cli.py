"""Command-line entry point for the V1 agent."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from .agent import CodingAgent
from .model import create_langchain_chat_model
from .schemas import AgentConfig, RunResult

_CONSOLE = Console()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ForgeCode V1 repository-aware coding agent")
    parser.add_argument(
        "task",
        nargs="?",
        help="Natural-language task for the agent (omit to start interactive mode)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start interactive mode (also used when task is omitted)",
    )
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
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key; prefer FORGECODE_API_KEY or OPENAI_API_KEY in the environment",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "OpenAI-compatible endpoint; prefer FORGECODE_BASE_URL, "
            "OPENAI_BASE_URL, or OPENAI_API_BASE"
        ),
    )
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--show-trace", action="store_true", help="Print messages and tool results")
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming output and wait for the complete model response",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        model = create_langchain_chat_model(
            model=args.model,
            api_key=args.api_key,
            base_url=args.base_url,
        )
        agent = CodingAgent.for_workspace(
            model=model,
            workspace_root=args.workspace,
            config=AgentConfig(max_steps=args.max_steps),
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ForgeCode error: {exc}")
        return 2

    if args.interactive or args.task is None:
        return _interactive_loop(
            agent,
            show_trace=args.show_trace,
            stream=not args.no_stream,
            initial_task=args.task,
        )

    result, streamed = _execute_task(
        agent, args.task, history=None, stream=not args.no_stream
    )
    if result is None:
        return 2
    return _print_result(result, show_trace=args.show_trace, streamed=streamed)


def _interactive_loop(
    agent: CodingAgent,
    *,
    show_trace: bool,
    initial_task: str | None = None,
    stream: bool,
) -> int:
    """连续读取任务，并把上一次消息历史交给下一次运行。"""

    history: list[Any] | None = None
    print("ForgeCode interactive mode. Type :help for commands.")

    if initial_task:
        result, streamed = _execute_task(agent, initial_task, history=None, stream=stream)
        if result is not None:
            history = result.messages
            _print_result(result, show_trace=show_trace, streamed=streamed)

    while True:
        try:
            raw_task = input("forge> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\nUse :quit to exit.")
            continue

        task = raw_task.strip()
        if not task:
            continue

        command = task.casefold()
        if command in {":quit", ":q", "quit", "exit"}:
            print("Bye.")
            break
        if command == ":help":
            _print_interactive_help()
            continue
        if command in {":clear", ":reset"}:
            history = None
            print("Conversation history cleared.")
            continue

        result, streamed = _execute_task(agent, task, history=history, stream=stream)
        if result is not None:
            history = result.messages
            _print_result(result, show_trace=show_trace, streamed=streamed)

    return 0


def _print_interactive_help() -> None:
    """Print commands that are handled locally instead of sent to the model."""

    print("Commands:")
    print("  :help          Show this help")
    print("  :clear / :reset Clear conversation history")
    print("  :quit / :q     Exit ForgeCode")
    print("  exit / quit    Exit ForgeCode")


def _execute_task(
    agent: CodingAgent,
    task: str,
    *,
    history: list[Any] | None,
    stream: bool,
) -> tuple[RunResult | None, bool]:
    """Run one task and turn user-facing setup errors into a readable message."""
    try:
        if not stream:
            return agent.run(task, history=history), False

        streamer = _MarkdownStreamer()
        with streamer:
            result = agent.run(task, history=history, on_text=streamer.write)
        return result, streamer.rendered
    except (RuntimeError, ValueError) as exc:
        print(f"ForgeCode error: {exc}")
        return None, False


def _print_result(result: RunResult, *, show_trace: bool, streamed: bool = False) -> int:
    """Print one result and return the process status used by one-shot mode."""

    if show_trace:
        print("--- trace ---")
        for message in result.messages:
            print(
                json.dumps(
                    _message_to_dict(message),
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
        print("--- end trace ---")

    if result.stop_reason.value == "completed":
        if not streamed:
            _print_markdown(result.final_text)
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


def _print_markdown(text: str) -> None:
    """Render a completed assistant answer as Markdown in the terminal."""

    if text.strip():
        _CONSOLE.print(Markdown(text))
    else:
        _CONSOLE.print()


class _MarkdownStreamer:
    """Incrementally render assistant text while a LangChain stream is open."""

    def __init__(self) -> None:
        self._text = ""
        self._live: Live | None = None
        self.rendered = False

    def __enter__(self) -> "_MarkdownStreamer":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._live is not None:
            self._live.stop()
        if self.rendered:
            _CONSOLE.print()

    def write(self, text: str) -> None:
        """Receive one text chunk from CodingAgent and refresh the live Markdown."""

        if not text:
            return
        if self._live is None:
            self._live = Live(
                Markdown(""),
                console=_CONSOLE,
                refresh_per_second=12,
            )
            self._live.start()
        self._text += text
        self.rendered = True
        self._live.update(Markdown(self._text), refresh=True)
