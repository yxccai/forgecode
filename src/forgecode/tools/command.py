"""A small, argv-based command tool for trusted local V0 demos."""

from __future__ import annotations

import subprocess
from typing import Any

from .base import Tool, ToolContext, ToolError


def run_command(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """在固定工作区执行 argv 命令，并返回退出码、标准输出和错误输出。"""

    argv = arguments.get("argv")
    timeout_seconds = float(arguments.get("timeout_seconds", 30))
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise ToolError("argv must be a non-empty list of strings")
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise ToolError("timeout_seconds must be between 0 and 120")

    try:
        completed = subprocess.run(
            argv,
            cwd=context.workspace_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ToolError(f"Executable not found: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return {
            "returncode": None,
            "timed_out": True,
            "stdout": context.limit_output(output),
            "stderr": "command timed out",
        }

    return {
        "returncode": completed.returncode,
        "timed_out": False,
        "stdout": context.limit_output(completed.stdout),
        "stderr": context.limit_output(completed.stderr),
    }


def command_tool() -> Tool:
    return Tool(
        name="run_command",
        description=(
            "Run an argv command in the repository workspace. Use this for trusted local "
            "inspection or tests; do not use shell syntax."
        ),
        parameters={
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Executable and arguments, for example "
                        "['python', '-m', 'pytest']."
                    ),
                },
                "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 120},
            },
            "required": ["argv"],
            "additionalProperties": False,
        },
        handler=run_command,
    )
