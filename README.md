# ForgeCode

ForgeCode 是一个用于学习 Agent 核心机制的轻量级终端 Coding Agent。

当前版本是 **V0 — Minimal Agent**：不使用 LangChain 或 LangGraph 的 Agent 高级封装，手写最基本的 Tool-Calling Loop：

```text
Model → Tool Call → Tool Execution → Tool Result → Model
```

## 代码结构

```text
src/forgecode/
├── cli.py                  # 命令行入口
├── agent.py                # Agent 主循环，建议第一个阅读
├── prompt_template.py      # system prompt
├── model.py                # ChatModel 与 OpenAI 适配器
├── schemas.py              # 消息、Tool Call、Tool Result
└── tools/
    ├── base.py             # Tool、Context、Registry
    ├── filesystem.py       # list / read / search
    └── command.py          # run_command
```

完整调用链见 [docs/architecture.md](docs/architecture.md)。

## 当前能力

- 浏览仓库文件：`list_files`
- 读取文本文件：`read_file`
- 搜索文本：`search_text`
- 在工作区执行 argv 命令：`run_command`
- 最大步骤数限制
- 工具错误反馈
- Tool 输出截断
- Fake Model 自动化测试
- OpenAI Chat Completions 适配器

## 初始化

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

设置 API Key：

```powershell
$env:OPENAI_API_KEY = "your-api-key"
```

运行一个代码理解任务：

```bash
forge "请先浏览仓库，然后说明项目的入口文件和主要模块" --show-trace
```

不使用 API Key 也可以运行确定性的 V0 演示：

```bash
python examples/v0_fake_demo.py
```

也可以指定工作区和模型：

```bash
forge "解释认证流程" --workspace . --model gpt-4o-mini --max-steps 8
```

## 测试

```bash
python -m pytest
```

测试不依赖真实模型，使用 Scripted/Fake Model 验证 Agent Loop 和工具边界。

## V0 重点阅读顺序

1. `src/forgecode/schemas.py`：消息、Tool Call、Tool Result 和运行结果；
2. `src/forgecode/tools/base.py`：Tool 注册、分发和错误边界；
3. `src/forgecode/agent.py`：手写 Agent Loop；
4. `src/forgecode/prompt_template.py`：系统提示词和 Agent 行为约束；
5. `tests/test_agent_loop.py`：用 Fake Model 回放完整循环；
6. `src/forgecode/model.py`：真实模型适配器。

完整版本路线见 [PROJECT_PLAN.md](PROJECT_PLAN.md)。
