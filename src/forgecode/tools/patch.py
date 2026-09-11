"""Apply unified-diff patches inside the configured workspace."""

from __future__ import annotations

import subprocess
from typing import Any

from .base import ToolContext, ToolError


def apply_patch(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Apply a unified diff with Git.

    The model supplies patch text, while the runtime controls the working
    directory and executes Git without a shell. This keeps the operation
    explicit and prevents shell interpolation from changing the command.
    """

    patch_text = arguments.get("patch")
    if not isinstance(patch_text, str) or not patch_text.strip():
        raise ToolError("patch must be a non-empty string")

    try:
        completed = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            cwd=context.workspace_root,
            input=patch_text,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ToolError("Git is not installed or is not available on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolError("git apply timed out after 30 seconds") from exc

    if completed.returncode != 0:
        message = completed.stderr.strip() or "git apply failed"
        raise ToolError(message)

    return {"applied": True, "message": "Patch applied successfully."}
