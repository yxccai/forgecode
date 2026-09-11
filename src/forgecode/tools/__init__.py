"""ForgeCode 的两套工具组装入口。

具体工具各自放在独立文件中；这里集中组装默认工具集合，让 Agent 的
初始化代码只需要读懂一个组装函数。V0 使用 ToolRegistry，V1 使用
LangChain 的 BaseTool 列表。
"""

from pathlib import Path

from .base import Tool, ToolContext, ToolError, ToolRegistry
from .command import command_tool
from .filesystem import list_files_tool, read_file_tool, search_text_tool
from .langchain_tools import create_langchain_tools


def create_default_registry(workspace_root: Path) -> ToolRegistry:
    """创建 V0 默认工具集合。

    ``AgentLoop`` 不直接知道每个工具的实现细节，只依赖这个组装函数。
    新增工具时，在这里注册即可。
    """

    context = ToolContext(workspace_root=workspace_root)
    registry = ToolRegistry(context)
    for tool in (list_files_tool(), read_file_tool(), search_text_tool(), command_tool()):
        registry.register(tool)
    return registry


__all__ = [
    "Tool",
    "ToolContext",
    "ToolError",
    "ToolRegistry",
    "create_default_registry",
    "create_langchain_tools",
]
