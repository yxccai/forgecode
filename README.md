# ForgeCode

ForgeCode 是一个用于学习 Agent 核心机制的轻量级终端 Coding Agent。

当前版本是 **V1 — LangChain Tools + 可控 Coding Loop**。V1 使用 LangChain 的标准消息和工具抽象，但仍然保留显式循环，让每一轮模型调用、工具执行和 Observation 回填都清清楚楚：

~~~text
HumanMessage → AIMessage(tool_calls) → BaseTool.invoke → ToolMessage → 下一轮
~~~

V0 没有被删除，保存在 agent_v0.py 和 docs/versions/v0.md 中，方便对比“手写字典协议”与“标准消息协议”的差异。

## 代码结构

~~~text
src/forgecode/
├── cli.py                    # 命令行入口
├── agent.py                  # V1 CodingAgent 主循环，建议第一个阅读
├── agent_v0.py               # V0 AgentLoop，保留用于版本对照
├── prompt_template.py        # system prompt
├── model.py                  # V0/V1 模型适配器
├── schemas.py                # AgentConfig、RunResult、统计和停止原因
└── tools/
    ├── base.py               # ToolContext、路径边界、V0 Registry
    ├── filesystem.py         # list / read / search 底层实现
    ├── command.py            # 不经过 shell 执行 argv
    ├── git.py                # git diff HEAD
    ├── patch.py              # git apply unified diff
    └── langchain_tools.py    # @tool 适配器和参数 schema
~~~

V1 调用链见 [docs/architecture-v1.md](docs/architecture-v1.md)，版本学习笔记见 [docs/versions/v1.md](docs/versions/v1.md)。

## 当前能力

- 浏览仓库文件：list_files
- 读取文本文件：read_file
- 搜索文本：search_text
- 在工作区执行 argv 命令：run_command
- 应用 unified diff：apply_patch
- 查看 staged 和 unstaged 代码变化：git_diff
- 交互式多轮 CLI 与会话历史
- 工具错误反馈和输出截断
- 最大步骤数限制
- LangChain AIMessage / ToolMessage 消息轨迹
- 单元测试中的隔离模型替身
- OpenAI ChatOpenAI 适配器

## 初始化

~~~bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
~~~

设置 API 配置：

ForgeCode 使用 LangChain ChatOpenAI，可以连接 OpenAI 或任何兼容 OpenAI Chat Completions 接口的第三方服务。推荐使用环境变量：

~~~powershell
$env:FORGECODE_API_KEY = "your-api-key"
$env:FORGECODE_BASE_URL = "https://your-provider.example/v1"
$env:FORGECODE_MODEL = "your-model-name"
~~~

也兼容 OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_API_BASE。命令行参数可以临时覆盖环境变量：

~~~bash
forge "解释认证流程" --api-key your-api-key --base-url https://your-provider.example/v1 --model your-model-name
~~~

运行一个代码理解或修改任务：

~~~bash
forge "请先浏览仓库，然后说明项目的入口文件和主要模块" --show-trace
forge "把 README 的标题改得更清晰，并运行相关检查" --max-steps 8
~~~

如果不想每次重新输入命令，可以启动连续对话模式：

~~~bash
forge
# 或者显式指定
forge --interactive
~~~

启动后可以连续输入多个任务：

~~~text
forge> 请先看看认证相关代码
forge> 刚才提到的入口文件在哪里？
forge> :clear
forge> :quit
~~~

交互模式会保留当前会话的消息历史；`:clear`/`:reset` 清空历史，`:quit`/`:q` 退出。

回答会用 Rich 渲染 Markdown，并默认通过 LangChain `stream()` 增量更新。
如果第三方服务不支持流式接口，可以关闭流式输出：

~~~bash
forge --no-stream
~~~
## 测试

~~~bash
pytest -q
ruff check src tests
~~~

单元测试会隔离模型调用，验证 Agent Loop、工具错误、代码修改和 Git diff；运行 CLI 时始终走真实 API。

## 推荐阅读顺序

1. [docs/versions/v1.md](docs/versions/v1.md)：先理解本版问题和消息流；
2. src/forgecode/schemas.py：运行结果、统计和停止原因；
3. src/forgecode/tools/base.py：工作区边界与输出限制；
4. src/forgecode/tools/langchain_tools.py：@tool 如何包装底层 handler；
5. src/forgecode/agent.py：V1 显式循环；
6. tests/test_coding_agent.py：验证消息循环、工具结果和停止条件；
7. src/forgecode/model.py：真实 ChatOpenAI 工厂；
8. docs/versions/v0.md 和 src/forgecode/agent_v0.py：回看 V0 的手写实现。

完整版本路线见 [PROJECT_PLAN.md](PROJECT_PLAN.md)。
