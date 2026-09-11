"""LangChain adapters for ForgeCode's repository tools.

The lower-level handlers in filesystem.py, command.py, git.py and patch.py
own path validation and subprocess policy. The functions in this module only
translate typed Python arguments into LangChain tools and serialize the
results. Keeping those responsibilities separate makes the code easier to
read and test.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, tool

from .base import ToolContext
from .command import run_command as run_command_impl
from .filesystem import (
    list_files as list_files_impl,
)
from .filesystem import (
    read_file as read_file_impl,
)
from .filesystem import (
    search_text as search_text_impl,
)
from .git import git_diff as git_diff_impl
from .patch import apply_patch as apply_patch_impl


def create_langchain_tools(context: ToolContext) -> list[BaseTool]:
    """Build the six tools exposed to a V1 model.

    The closures capture one ToolContext, so every tool call uses the same
    workspace and the same output limits.
    """

    @tool
    def list_files(path: str = ".", max_entries: int = 200) -> str:
        """列出工作区内的文件；path 是相对工作区的目录。"""
        result = list_files_impl(
            {"path": path, "max_entries": max_entries},
            context,
        )
        return _json(result)

    @tool
    def read_file(path: str, start_line: int = 1, end_line: int = 250) -> str:
        """读取工作区文件的指定行范围，返回带行号的内容。"""
        result = read_file_impl(
            {"path": path, "start_line": start_line, "end_line": end_line},
            context,
        )
        return _json(result)

    @tool
    def search_text(query: str, path: str = ".", max_results: int = 50) -> str:
        """在工作区内搜索文本，返回匹配文件、行号和内容。"""
        result = search_text_impl(
            {"query": query, "path": path, "max_results": max_results},
            context,
        )
        return _json(result)

    @tool
    def run_command(argv: list[str], timeout_seconds: float = 30) -> str:
        """在工作区运行一个不经过 shell 的命令。"""
        result = run_command_impl(
            {"argv": argv, "timeout_seconds": timeout_seconds},
            context,
        )
        return _json(result)

    @tool
    def apply_patch(patch: str) -> str:
        """应用一个 unified diff，用于创建或修改工作区文件。"""
        result = apply_patch_impl({"patch": patch}, context)
        return _json(result)

    @tool
    def git_diff(path: str = "") -> str:
        """查看工作区相对 HEAD 的 Git diff，可选地限制到某个路径。"""
        result = git_diff_impl({"path": path}, context)
        return _json(result)

    return [list_files, read_file, search_text, run_command, apply_patch, git_diff]


def _json(value: Any) -> str:
    """把工具结果稳定地序列化为模型可以阅读的 JSON。"""

    return json.dumps(value, ensure_ascii=False, default=str)
