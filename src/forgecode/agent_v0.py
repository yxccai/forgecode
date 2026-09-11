"""V0 的 Agent 主循环。

这是整个项目最值得先读懂的文件。它只做三件事：

1. 把消息和工具 Schema 交给模型；
2. 执行模型返回的 Tool Call；
3. 把 Tool Result 放回消息历史，继续下一轮。

提示词在 ``prompt_template.py``，模型调用在 ``model.py``，工具实现
在 ``tools/``。把这些职责拆开后，可以沿着一个清晰的调用链学习 Agent。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .model import ChatModel
from .prompt_template import build_system_prompt
from .schemas import AgentConfig, Message, ModelResponse, RunResult, RunStats, StopReason
from .tools import ToolRegistry, create_default_registry


@dataclass
class AgentLoop:
    """不依赖 Agent 框架的最小运行时。"""

    model: ChatModel
    registry: ToolRegistry
    config: AgentConfig = field(default_factory=AgentConfig)
    system_prompt: str = ""

    @classmethod
    def for_workspace(
        cls,
        model: ChatModel,
        workspace_root: Path,
        config: AgentConfig | None = None,
    ) -> "AgentLoop":
        """为一个工作区组装 Agent。

        这是应用层的组装入口：创建工具集合，并生成本次运行的系统提示词。
        ``run`` 本身不关心工具是如何创建的。
        """

        registry = create_default_registry(workspace_root)
        return cls(
            model=model,
            registry=registry,
            config=config or AgentConfig(),
            system_prompt=build_system_prompt(registry.context.workspace_root),
        )

    def run(self, task: str) -> RunResult:
        """执行一个任务，直到模型给出最终回答或触发停止条件。"""

        if not task.strip():
            raise ValueError("task must not be empty")

        # messages 是 Agent 的短期记忆。每次模型调用都能看到完整对话历史，
        # 包括之前的 assistant Tool Call 和 tool Observation。
        messages: list[Message] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]
        stats = RunStats()

        for step in range(1, self.config.max_steps + 1):
            stats.steps = step
            try:
                # 模型负责“决定下一步”，但不直接执行本地操作。
                response = self.model.complete(messages, self.registry.definitions())
            except Exception as exc:
                stats.model_calls += 1
                return RunResult(
                    final_text="",
                    stop_reason=StopReason.MODEL_ERROR,
                    messages=messages,
                    stats=stats,
                    error=f"{type(exc).__name__}: {exc}",
                )

            stats.model_calls += 1
            # 先把 assistant 的响应放入历史。若它包含 Tool Call，下一轮
            # 的 tool message 就会和这条 assistant message 配对。
            messages.append(response.raw_message or _assistant_message(response))

            if response.is_final:
                # 没有 Tool Call 表示模型认为任务已经可以回答了。
                return RunResult(
                    final_text=response.content or "",
                    stop_reason=StopReason.COMPLETED,
                    messages=messages,
                    stats=stats,
                )

            for call in response.tool_calls:
                stats.tool_calls += 1
                # Runtime 根据工具名分发调用；工具失败也会转成 Observation，
                # 这样模型有机会修正参数或选择另一条路径。
                result = self.registry.execute(call)
                if not result.ok:
                    stats.tool_errors += 1
                messages.append(result.as_message())

        # 不能无限循环。达到预算时返回明确的停止原因，而不是假装完成。
        return RunResult(
            final_text="",
            stop_reason=StopReason.STEP_LIMIT,
            messages=messages,
            stats=stats,
            error=f"Agent reached max_steps={self.config.max_steps}",
        )


def _assistant_message(response: ModelResponse) -> Message:
    """为 Fake Model 等没有提供原始消息的实现补一个 assistant message。"""

    message: Message = {"role": "assistant", "content": response.content}
    if response.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": _arguments_json(call.arguments),
                },
            }
            for call in response.tool_calls
        ]
    return message


def _arguments_json(arguments: dict) -> str:
    """把 Tool Call 参数编码成 OpenAI message 使用的 JSON 字符串。"""

    import json

    return json.dumps(arguments, ensure_ascii=False)
