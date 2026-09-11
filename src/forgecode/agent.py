"""V1 coding agent built on LangChain messages and typed tools.

V0 用自定义字典和 ToolRegistry 表达消息与工具调用；V1 改用
HumanMessage、SystemMessage、AIMessage、ToolMessage 以及 @tool 生成的
结构化工具 schema。运行时仍然保留一个显式循环，因此每一步如何发生
都能直接阅读和调试，不引入 LangGraph 或隐藏的状态机。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from .model import LangChainChatModel
from .prompt_template import build_system_prompt
from .schemas import AgentConfig, RunResult, RunStats, StopReason
from .tools import ToolContext, create_langchain_tools


@dataclass
class CodingAgent:
    """执行一次 repository-aware coding 任务的 V1 Agent。"""

    model: LangChainChatModel
    tools: list[BaseTool]
    config: AgentConfig = field(default_factory=AgentConfig)
    system_prompt: str = ""
    _tool_map: dict[str, BaseTool] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # 用工具名建立索引，让模型返回的 tool_call 可以 O(1) 找到实现。
        self._tool_map = {tool.name: tool for tool in self.tools}

    @classmethod
    def for_workspace(
        cls,
        model: LangChainChatModel,
        workspace_root: str,
        config: AgentConfig | None = None,
    ) -> "CodingAgent":
        """为一个工作区创建完整的 V1 工具集合。"""

        context = ToolContext(workspace_root)
        tools = create_langchain_tools(context)
        return cls(
            model=model,
            tools=tools,
            config=config or AgentConfig(),
            system_prompt=build_system_prompt(context.workspace_root),
        )

    def run(self, task: str) -> RunResult:
        """运行显式的 model -> tools -> observation 循环。"""

        if not task.strip():
            raise ValueError("task must not be empty")

        messages: list[Any] = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=task),
        ]
        stats = RunStats()

        # bind_tools 只做一次：它把工具 JSON schema 绑定到模型实例。
        model_with_tools = self.model.bind_tools(self.tools)

        for step in range(1, self.config.max_steps + 1):
            stats.steps = step

            try:
                # 每一轮把完整消息轨迹交给模型，模型返回一个 AIMessage。
                ai_message = model_with_tools.invoke(messages)
            except Exception as exc:
                return RunResult(
                    final_text="",
                    stop_reason=StopReason.MODEL_ERROR,
                    messages=messages,
                    stats=stats,
                    error=str(exc),
                )

            stats.model_calls += 1
            messages.append(ai_message)

            # LangChain 已经把工具调用解析成 AIMessage.tool_calls。
            tool_calls = list(getattr(ai_message, "tool_calls", []) or [])
            if not tool_calls:
                return RunResult(
                    final_text=_content_to_text(getattr(ai_message, "content", "")),
                    stop_reason=StopReason.COMPLETED,
                    messages=messages,
                    stats=stats,
                )

            # 一个 AIMessage 可能包含多个并行 tool_call；逐个执行并反馈结果。
            for raw_call in tool_calls:
                stats.tool_calls += 1
                tool_name = str(raw_call.get("name", ""))
                tool_call_id = str(raw_call.get("id", "")) or f"call-{stats.tool_calls}"
                arguments = raw_call.get("args", {}) or {}
                tool = self._tool_map.get(tool_name)

                if tool is None:
                    stats.tool_errors += 1
                    observation = _error_observation(f"Unknown tool: {tool_name}")
                else:
                    try:
                        observation = _stringify(tool.invoke(arguments))
                    except Exception as exc:
                        # 工具失败也要变成 observation，模型才有机会自行修正。
                        stats.tool_errors += 1
                        observation = _error_observation(str(exc))

                # tool_call_id 是模型调用与工具结果之间的关联键，不能省略。
                messages.append(
                    ToolMessage(
                        content=observation,
                        tool_call_id=tool_call_id,
                        name=tool_name or None,
                    )
                )

        return RunResult(
            final_text="",
            stop_reason=StopReason.STEP_LIMIT,
            messages=messages,
            stats=stats,
            error=f"Agent reached max_steps={self.config.max_steps}",
        )


def _stringify(value: Any) -> str:
    """将工具返回值统一成文本，便于放进 ToolMessage。"""

    if isinstance(value, str):
        return value
    return str(value)


def _error_observation(message: str) -> str:
    """返回结构稳定的错误 observation，让模型知道这次调用失败。"""

    return '{"ok": false, "error": ' + repr(message) + "}"


def _content_to_text(content: Any) -> str:
    """兼容 LangChain 内容可能是字符串或多模态 block 列表。"""

    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", block)))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)
