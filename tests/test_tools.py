from __future__ import annotations

import json
from pathlib import Path

from forgecode.schemas import ToolCall
from forgecode.tools import ToolContext, ToolRegistry
from forgecode.tools.command import command_tool
from forgecode.tools.filesystem import list_files_tool, read_file_tool, search_text_tool


def registry_for(path: Path, max_output_chars: int = 12_000) -> ToolRegistry:
    registry = ToolRegistry(ToolContext(path, max_output_chars=max_output_chars))
    for tool in (list_files_tool(), read_file_tool(), search_text_tool(), command_tool()):
        registry.register(tool)
    return registry


def test_filesystem_tools_list_read_and_search(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "secret.txt").write_text("hello", encoding="utf-8")
    registry = registry_for(tmp_path)

    files = registry.execute(ToolCall("1", "list_files", {}))
    read = registry.execute(ToolCall("2", "read_file", {"path": "src/app.py"}))
    search = registry.execute(ToolCall("3", "search_text", {"query": "hello"}))

    assert files.ok
    assert "src/" in json.loads(files.content)
    assert ".git/secret.txt" not in files.content
    assert read.ok and "2:     return 'hello'" in read.content
    assert search.ok
    matches = json.loads(search.content)
    assert matches == [{"path": "src/app.py", "line": 2, "text": "return 'hello'"}]


def test_paths_cannot_escape_workspace(tmp_path: Path) -> None:
    registry = registry_for(tmp_path)
    result = registry.execute(ToolCall("1", "read_file", {"path": "../outside.txt"}))

    assert not result.ok
    assert "outside the workspace" in result.content


def test_read_file_handles_empty_text_file(tmp_path: Path) -> None:
    (tmp_path / "empty.txt").write_text("", encoding="utf-8")
    registry = registry_for(tmp_path)

    result = registry.execute(ToolCall("1", "read_file", {"path": "empty.txt"}))

    assert result.ok
    assert result.content == "(file is empty)"


def test_tool_output_is_truncated(tmp_path: Path) -> None:
    (tmp_path / "large.txt").write_text("x" * 300, encoding="utf-8")
    registry = registry_for(tmp_path, max_output_chars=100)
    result = registry.execute(ToolCall("1", "read_file", {"path": "large.txt"}))

    assert result.ok
    assert len(result.content) > 40  # truncation marker is part of the observation
    assert "truncated" in result.content


def test_command_tool_uses_workspace_and_returns_exit_code(tmp_path: Path) -> None:
    registry = registry_for(tmp_path)
    result = registry.execute(
        ToolCall("1", "run_command", {"argv": ["python", "-c", "print('ok')"]})
    )

    assert result.ok
    payload = json.loads(result.content)
    assert payload["returncode"] == 0
    assert payload["stdout"].strip() == "ok"
