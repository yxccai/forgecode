"""Git-related tools used by the V1 coding agent.

The raw handler stays independent from LangChain. This keeps the filesystem
boundary easy to test and makes it possible to reuse the operation from a
different runtime later.
"""

from __future__ import annotations

import subprocess
from typing import Any

from .base import ToolContext, ToolError


def git_diff(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Return the working-tree diff relative to HEAD.

    A path is resolved inside the configured workspace before it is passed to
    Git. Using HEAD includes both staged and unstaged changes, which makes the
    result useful while an agent is iterating on a patch.
    """

    requested_path = str(arguments.get("path", "")).strip()
    command = ["git", "diff", "HEAD"]

    if requested_path:
        resolved_path = context.resolve_path(requested_path)
        relative_path = resolved_path.relative_to(context.workspace_root).as_posix()
        command.extend(["--", relative_path])

    try:
        completed = subprocess.run(
            command,
            cwd=context.workspace_root,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ToolError("Git is not installed or is not available on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolError("git diff timed out after 30 seconds") from exc

    if completed.returncode != 0:
        message = completed.stderr.strip() or "git diff failed"
        raise ToolError(message)

    diff = context.limit_output(completed.stdout)
    return {"has_changes": bool(completed.stdout.strip()), "diff": diff}
