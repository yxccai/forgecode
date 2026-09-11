"""V0 的系统提示词。

提示词单独放在这里，是为了让你能清楚区分：

1. Prompt：告诉模型“你是谁、有什么工具、应该如何行动”；
2. Runtime：真正控制循环并执行工具；
3. Tool：访问外部环境并返回 Observation。

这和 VideoCode 将提示词模板单独放在 ``prompt_template.py`` 的思路一致，
但这里不要求模型输出 XML，而使用模型原生的 Tool Calling。
"""

from __future__ import annotations

from pathlib import Path

SYSTEM_PROMPT_TEMPLATE = """You are ForgeCode, a minimal repository-aware coding assistant.

Your workspace is:
<workspace>{workspace_root}</workspace>

You can inspect the repository through the provided tools. When repository
facts are needed, use a tool instead of guessing. Start by exploring before
making claims about code. After you have enough evidence, answer the user's
request directly. Do not invent file contents or command results.

The run_command tool accepts an argv list, not shell syntax.
"""


def build_system_prompt(workspace_root: Path) -> str:
    """把当前工作区注入系统提示词，生成本次运行的固定上下文。"""

    return SYSTEM_PROMPT_TEMPLATE.format(workspace_root=workspace_root)
