"""工具层的公共定义。

阅读顺序建议是：

1. 先看 ``Tool``：一个工具由名称、描述、Schema 和 Python handler 组成；
2. 再看 ``ToolRegistry.execute``：它负责根据模型给出的名称分发工具；
3. 最后看具体工具：它们只负责自己的环境操作。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..schemas import ToolCall, ToolExecutionResult


class ToolError(Exception):
    """预期内、并且应该反馈给模型继续处理的工具错误。"""


@dataclass(frozen=True)
class ToolContext:
    """工具共享的运行环境。

    V0 中所有文件操作都必须通过这个 Context 解析，避免每个工具各自
    处理工作区路径，导致行为不一致。
    """

    workspace_root: Path
    max_output_chars: int = 12_000

    def __post_init__(self) -> None:
        root = self.workspace_root.expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"workspace_root must be an existing directory: {root}")
        if self.max_output_chars < 100:
            raise ValueError("max_output_chars must be at least 100")
        object.__setattr__(self, "workspace_root", root)

    def resolve_path(self, relative_path: str) -> Path:
        """把相对路径解析到工作区，并拒绝越过工作区根目录。"""

        candidate = (self.workspace_root / relative_path).resolve()
        if candidate != self.workspace_root and self.workspace_root not in candidate.parents:
            raise ToolError(f"Path is outside the workspace: {relative_path}")
        return candidate

    def limit_output(self, text: str) -> str:
        """限制 Observation 大小，同时告诉模型结果被截断了。"""

        if len(text) <= self.max_output_chars:
            return text
        omitted = len(text) - self.max_output_chars
        return f"{text[: self.max_output_chars]}\n...[truncated {omitted} characters]"


ToolHandler = Callable[[dict[str, Any], ToolContext], Any]


@dataclass(frozen=True)
class Tool:
    """模型可见的工具描述，以及 Runtime 实际调用的 handler。"""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def definition(self) -> dict[str, Any]:
        """生成 OpenAI-compatible tools 参数。"""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """工具注册表：把模型的 Tool Call 转成 Tool Result。"""

    def __init__(self, context: ToolContext) -> None:
        self.context = context
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册一个工具；名称重复通常意味着配置错误。"""

        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def definitions(self) -> list[dict[str, Any]]:
        """返回要传给模型的所有工具 Schema。"""

        return [tool.definition() for tool in self._tools.values()]

    def execute(self, call: ToolCall) -> ToolExecutionResult:
        """执行一次 Tool Call，并把所有错误转换成模型可见的 Observation。"""

        tool = self._tools.get(call.name)
        if tool is None:
            return self._error_result(call, f"Unknown tool: {call.name}")

        try:
            value = tool.handler(call.arguments, self.context)
            content = value if isinstance(value, str) else json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )
            return ToolExecutionResult(
                tool_call_id=call.id,
                tool_name=call.name,
                ok=True,
                content=self.context.limit_output(content),
            )
        except ToolError as exc:
            # 这是可预期的工具错误，例如文件不存在；模型可以据此调整下一步。
            return self._error_result(call, str(exc))
        except Exception as exc:  # pragma: no cover - 最后的 Runtime 边界
            # 未知异常也不能让整个 Agent 进程直接崩掉，要变成 Observation。
            return self._error_result(call, f"Tool failed: {type(exc).__name__}: {exc}")

    @staticmethod
    def _error_result(call: ToolCall, message: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_call_id=call.id,
            tool_name=call.name,
            ok=False,
            content=json.dumps({"ok": False, "error": message}, ensure_ascii=False),
        )
