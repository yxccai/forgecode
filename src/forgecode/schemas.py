"""V0 使用的数据结构。

这些类型故意保持简单：Agent 的核心不是复杂的对象层次，而是消息、
Tool Call 和 Tool Result 在循环中的流动。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# 这里使用接近 OpenAI Chat Completions 的字典形式，方便直接观察传给模型的内容。
Message = dict[str, Any]


class StopReason(StrEnum):
    """一次 Agent 运行结束的原因。"""

    COMPLETED = "completed"
    STEP_LIMIT = "step_limit"
    MODEL_ERROR = "model_error"


@dataclass(frozen=True)
class ToolCall:
    """模型要求 Runtime 执行的一次工具调用。"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelResponse:
    """把不同模型 SDK 的响应统一成 Agent 能理解的格式。"""

    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    # raw_message 保留模型原始 assistant message，便于下一轮继续发送。
    raw_message: Message = field(default_factory=dict)

    @property
    def is_final(self) -> bool:
        """没有 Tool Call 时，当前响应就是最终回答。"""

        return not self.tool_calls


@dataclass(frozen=True)
class ToolExecutionResult:
    """工具执行后返回给模型的 Observation。"""

    tool_call_id: str
    tool_name: str
    ok: bool
    content: str

    def as_message(self) -> Message:
        """把 Python 结果转换成下一轮模型请求中的 tool message。"""

        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "name": self.tool_name,
            "content": self.content,
        }


@dataclass(frozen=True)
class AgentConfig:
    """单次运行的最小控制参数。"""

    max_steps: int = 12

    def __post_init__(self) -> None:
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1")


@dataclass
class RunStats:
    """用于观察 Agent 行为的简单统计。"""

    steps: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    tool_errors: int = 0


@dataclass
class RunResult:
    """一次完整运行的结果和消息轨迹。"""

    final_text: str
    stop_reason: StopReason
    messages: list[Message]
    stats: RunStats
    error: str | None = None
