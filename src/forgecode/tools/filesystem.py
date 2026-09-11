"""Read-only repository exploration tools for V0."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Tool, ToolContext, ToolError

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
}


def _relative(path: Path, context: ToolContext) -> str:
    return path.relative_to(context.workspace_root).as_posix() or "."


def _is_probably_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return True
    return b"\x00" in sample


def list_files(arguments: dict[str, Any], context: ToolContext) -> list[str]:
    """递归列出工作区中的路径，过滤常见依赖和缓存目录。"""

    relative_path = str(arguments.get("path", "."))
    max_entries = int(arguments.get("max_entries", 200))
    if max_entries < 1 or max_entries > 1_000:
        raise ToolError("max_entries must be between 1 and 1000")

    root = context.resolve_path(relative_path)
    if not root.exists():
        raise ToolError(f"Path does not exist: {relative_path}")
    if not root.is_dir():
        raise ToolError(f"Path is not a directory: {relative_path}")

    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        entries.append(_relative(path, context) + ("/" if path.is_dir() else ""))
        if len(entries) >= max_entries:
            break
    return entries


def read_file(arguments: dict[str, Any], context: ToolContext) -> str:
    """读取文本文件的指定行，并给每行加上行号帮助模型定位。"""

    relative_path = str(arguments.get("path", ""))
    if not relative_path:
        raise ToolError("path is required")
    path = context.resolve_path(relative_path)
    if not path.exists():
        raise ToolError(f"File does not exist: {relative_path}")
    if not path.is_file():
        raise ToolError(f"Path is not a file: {relative_path}")
    if _is_probably_binary(path):
        raise ToolError(f"Refusing to read a binary file: {relative_path}")

    start_line = max(1, int(arguments.get("start_line", 1)))
    end_line = int(arguments.get("end_line", start_line + 250 - 1))
    if end_line < start_line:
        raise ToolError("end_line must be greater than or equal to start_line")
    if end_line - start_line + 1 > 500:
        raise ToolError("A single read may contain at most 500 lines")

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ToolError(f"File is not valid UTF-8 text: {relative_path}") from exc
    if not lines:
        return "(file is empty)"
    selected = lines[start_line - 1 : end_line]
    if not selected:
        raise ToolError(f"No lines in requested range: {relative_path}")
    numbered = [f"{number}: {line}" for number, line in enumerate(selected, start=start_line)]
    return "\n".join(numbered)


def search_text(arguments: dict[str, Any], context: ToolContext) -> list[dict[str, Any]]:
    """在文本文件中做简单的不区分大小写搜索。"""

    query = str(arguments.get("query", ""))
    if not query:
        raise ToolError("query is required")
    relative_path = str(arguments.get("path", "."))
    max_results = int(arguments.get("max_results", 50))
    if max_results < 1 or max_results > 500:
        raise ToolError("max_results must be between 1 and 500")

    root = context.resolve_path(relative_path)
    if not root.exists():
        raise ToolError(f"Path does not exist: {relative_path}")
    candidates = [root] if root.is_file() else sorted(root.rglob("*"))
    results: list[dict[str, Any]] = []
    for path in candidates:
        if not path.is_file() or any(part in _SKIP_DIRS for part in path.parts):
            continue
        if _is_probably_binary(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines, start=1):
            if query.lower() not in line.lower():
                continue
            results.append(
                {
                    "path": _relative(path, context),
                    "line": line_number,
                    "text": line.strip(),
                }
            )
            if len(results) >= max_results:
                return results
    return results


def list_files_tool() -> Tool:
    return Tool(
        name="list_files",
        description="List files and directories inside the repository workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative directory path."},
                "max_entries": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            "additionalProperties": False,
        },
        handler=list_files,
    )


def read_file_tool() -> Tool:
    return Tool(
        name="read_file",
        description="Read a UTF-8 text file with line numbers.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path."},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=read_file,
    )


def search_text_tool() -> Tool:
    return Tool(
        name="search_text",
        description="Search text in repository files and return matching paths and line numbers.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to search for."},
                "path": {"type": "string", "description": "Relative file or directory path."},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=search_text,
    )
