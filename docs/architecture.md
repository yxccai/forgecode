# ForgeCode V0 代码结构（历史版本）

V0 按照“应用入口 → Agent 主循环 → 模型 / 提示词 / 工具”的方向组织代码。
V1 的新调用链见 [architecture-v1.md](architecture-v1.md)。
阅读时从 `agent_v0.py` 开始，不需要先理解整个项目。

```text
用户命令
   │
   ▼
cli.py                         只负责解析参数、创建 Agent、打印结果
   │
   ▼
agent_v0.py                       只负责 Agent Loop
   │        ├── prompt_template.py   生成 system message
   │        ├── model.py             调用模型并解析响应
   │        └── tools/
   │              ├── base.py        Tool、Context、Registry
   │              ├── filesystem.py  list / read / search
   │              └── command.py     run_command
   │
   ▼
schemas.py                     消息、Tool Call、Tool Result、Run Result
```

## 一次请求的调用链

```text
AgentLoop.run(task)
  │
  ├─ 1. 创建 [system message, user message]
  │
  ├─ 2. model.complete(messages, tool_definitions)
  │       └─ 返回最终文本，或者一个 / 多个 ToolCall
  │
  ├─ 3. registry.execute(tool_call)
  │       └─ 找到对应 handler，得到 ToolExecutionResult
  │
  ├─ 4. result.as_message()
  │       └─ 生成 role=tool 的 Observation，追加到 messages
  │
  └─ 5. 回到第 2 步，直到最终回答或达到 max_steps
```

## 为什么这样分层

### `agent_v0.py`：控制流程

它不实现文件读取，也不关心 OpenAI SDK 的具体对象。它只表达 Agent 的核心算法：

```text
请求模型 → 判断是否有工具调用 → 执行工具 → 追加观察 → 再请求模型
```

### `prompt_template.py`：行为约束

Prompt 决定模型如何理解自己的角色和工具，但 Prompt 本身不会执行任何操作。把它单独放置，可以独立修改和比较提示词。

### `model.py`：模型边界

`ChatModel` 是 Agent 需要的最小能力；`OpenAIChatModel` 只是一个具体适配器。Fake Model 因此可以替代真实模型测试控制逻辑。

### `tools/`：环境能力

工具把模型的结构化请求转换为本地环境操作，再把结果转换成 Observation。增加新工具时，先在对应文件定义，再到 `tools/__init__.py` 注册。

### `schemas.py`：数据流

把消息、调用和结果集中定义，方便沿着类型阅读一次完整数据流，也避免工具层和 Agent 层互相定义重复结构。

## 与 VideoCode 的关系

VideoCode 的相关示例把 Agent 主循环集中在 `agent_v0.py`，把提示词模板放在 `prompt_template.py`，工具作为普通函数提供。这种结构非常适合入门学习。ForgeCode 保留这个可读性，同时把模型适配器、数据结构和工具实现拆出，避免一个 `agent_v0.py` 同时承担所有职责。
