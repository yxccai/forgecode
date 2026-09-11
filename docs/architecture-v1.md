# V1 Architecture

V1 把调用链拆成四层，阅读代码时可以从上到下走一遍：

~~~text
CLI
 |
 +-- create_langchain_chat_model()
 |
 +-- CodingAgent.for_workspace()
       |
       +-- ToolContext(workspace_root)
       +-- create_langchain_tools(context)
       |      |
       |      +-- @tool list_files
       |      +-- @tool read_file
       |      +-- @tool search_text
       |      +-- @tool run_command
       |      +-- @tool apply_patch
       |      +-- @tool git_diff
       |
       +-- CodingAgent.run(task, history?)
              |
              +-- SystemMessage + HumanMessage
              +-- model.bind_tools(tools)
              +-- model.stream(messages) / invoke(messages)
              +-- AIMessage.tool_calls
              +-- BaseTool.invoke(args)
              +-- ToolMessage
              +-- repeat until final or max_steps
~~~

## 文件职责

| 文件 | 只负责什么 |
| --- | --- |
| cli.py | 参数解析、构造 Agent、打印结果 |
| model.py | V0 Chat Completions 适配器和 V1 ChatOpenAI 工厂 |
| agent.py | V1 的显式消息循环 |
| schemas.py | AgentConfig、RunResult、统计和停止原因 |
| tools/base.py | 工作区路径边界、输出大小和 V0 注册表 |
| tools/langchain_tools.py | 把原子 handler 适配为 LangChain BaseTool |
| tools/filesystem.py | 列文件、读文件、搜文本 |
| tools/command.py | 不经过 shell 执行命令 |
| tools/patch.py | 用 git apply 应用 unified diff |
| tools/git.py | 用 git diff HEAD 查看 staged 和 unstaged 变化 |

## 一轮循环的伪代码

~~~text
messages = [system, human]
runnable = model.bind_tools(tools)

for step in 1..max_steps:
    ai = stream_and_combine(runnable, messages)  # 或直接 invoke
    messages.append(ai)

    if ai.tool_calls is empty:
        return completed(ai.content)

    for call in ai.tool_calls:
        tool = tool_map[call.name]
        observation = tool.invoke(call.args)
        messages.append(ToolMessage(observation, call.id))

return step_limit
~~~

交互模式由 CLI 保存 `RunResult.messages`，下一轮通过 `run(task, history=...)` 继续；`:clear` 会丢弃这份历史。

V1 刻意不把这段逻辑隐藏在 AgentExecutor 或 LangGraph 中。学习阶段先掌握原始消息与工具协议，下一版再讨论状态图、重试节点、人工审批和持久化。
