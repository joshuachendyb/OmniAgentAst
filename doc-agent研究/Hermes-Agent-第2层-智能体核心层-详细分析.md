# Hermes Agent 第 2 层 · 智能体核心层 详细分析

> **父文档：** [Hermes-Agent-架构分析.md](./Hermes-Agent-架构分析.md)  
> **分析日期：** 2026-06-02  
> **代码仓库：** [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)  
> **分析路径：** `/mnt/f/agenttool/hermes/agent/`  
> **核心文件数：** 108 个 `.py` 文件  

---

## 目录

- [1. 概述](#1-概述)
- [2. 目录结构](#2-目录结构)
- [3. 核心文件依赖图](#3-核心文件依赖图)
- [4. AIAgent 初始化 (agent_init.py)](#4-aiagent-初始化-agent_initpy)
- [5. 核心对话循环 (conversation_loop.py)](#5-核心对话循环-conversation_looppy)
- [6. 系统提示词构建 (system_prompt.py + prompt_builder.py)](#6-系统提示词构建-system_promptpy--prompt_builderpy)
- [7. 上下文压缩 (context_compressor.py)](#7-上下文压缩-context_compressorpy)
- [8. 记忆系统 (memory_manager.py + memory_provider.py)](#8-记忆系统-memory_managerpy--memory_providerpy)
- [9. Provider 适配器层](#9-provider-适配器层)
- [10. 工具执行与安全](#10-工具执行与安全)
- [11. 关键技术细节](#11-关键技术细节)
- [12. 设计要点总结](#12-设计要点总结)

---

## 1. 概述

智能体核心层是 Hermes 的"大脑"，负责：

| 职责 | 对应模块 |
|------|----------|
| Agent 实例初始化 | `agent_init.py` (1,657行) |
| 多轮对话循环 | `conversation_loop.py` (4,707行) |
| 系统提示词构建 | `system_prompt.py` (407行) + `prompt_builder.py` (1,507行) |
| 上下文自动压缩 | `context_compressor.py` (2,078行) |
| 跨会话记忆 | `memory_manager.py` (653行) + `memory_provider.py` (336行) |
| 多 Provider 适配 | `anthropic_adapter.py`, `codex_responses_adapter.py`, `bedrock_adapter.py`, `gemini_native_adapter.py` 等 |
| 工具安全检查 | `tool_executor.py` (1,016行), `tool_guardrails.py` (415行) |

**设计理念：** 所有核心逻辑从 `run_agent.py` 的 `AIAgent` 类中提取到 `agent/` 目录，`run_agent.py` 只保留薄壳 Forwarder 方法。

---

## 2. 目录结构

```
agent/
├── agent_init.py              # AIAgent.__init__ 实际实现 (1,657行)
├── conversation_loop.py       # 核心对话循环 (4,707行)
├── system_prompt.py           # 提示词组装编排 (407行)
├── prompt_builder.py          # 提示词各组成部分构建 (1,507行)
│
├── context_compressor.py      # 上下文自动压缩 (2,078行)
├── conversation_compression.py # 压缩辅助 (795行)
├── context_engine.py          # 上下文引擎 ABC 基类 (226行)
│
├── memory_manager.py          # 记忆管理器 (653行)
├── memory_provider.py         # 记忆 Provider ABC (336行)
│
├── anthropic_adapter.py       # Anthropic 消息格式适配 (2,303行)
├── codex_responses_adapter.py # OpenAI Codex/Responses 适配 (1,260行)
├── bedrock_adapter.py         # AWS Bedrock 适配 (1,277行)
├── gemini_native_adapter.py   # Gemini 原生 API 适配 (971行)
├── gemini_cloudcode_adapter.py # Gemini CloudCode 适配 (735行)
├── azure_identity_adapter.py  # Azure 托管身份适配 (714行)
├── chat_completion_helpers.py # Chat Completion 调用辅助 (2,457行)
├── agent_runtime_helpers.py   # 运行时辅助函数 (2,361行)
│
├── tool_executor.py           # 同步+异步工具执行 (1,016行)
├── tool_guardrails.py         # 工具调用护栏 (415行)
├── tool_dispatch_helpers.py   # 工具派发辅助 (367行)
├── tool_result_classification.py # 工具结果分类
│
├── model_metadata.py          # 模型元数据/上下文长度 (1,854行)
├── iteration_budget.py        # 迭代预算管理 (55行)
│
├── auxiliary_client.py        # 辅助模型客户端 (5,662行)
├── credential_pool.py         # 凭证池管理 (2,182行)
├── credential_persistence.py  # 凭证持久化 (121行)
├── credential_sources.py      # 凭证来源 (456行)
│
├── error_classifier.py        # API 错误分类 (1,316行)
├── redact.py                  # 密钥脱敏 (488行)
├── message_sanitization.py    # 消息清洗 (416行)
├── display.py                 # KawaiiSpinner 动画 (1,033行)
│
├── think_scrubber.py          # 思考内容擦除 (349行)
├── prompt_caching.py          # Anthropic 前缀缓存 (62行)
├── skill_commands.py          # 技能斜杠命令 (496行)
├── skill_utils.py             # 技能工具函数 (498行)
│
├── retry_utils.py             # 重试工具 (51行)
├── rate_limit_tracker.py      # 速率跟踪 (195行)
├── async_utils.py             # 异步工具 (66行)
├── subdirectory_hints.py      # 子目录提示 (249行)
│
├── context_references.py      # 上下文引用 (984行)
├── shell_hooks.py             # Shell 钩子 (709行)
│
├── transcription_provider.py  # 语音转录 Provider (182行)
├── transcription_registry.py  # 转录注册表 (106行)
├── tts_provider.py            # TTS Provider (263行)
├── tts_registry.py            # TTS 注册表 (112行)
├── image_gen_provider.py      # 图像生成 Provider (266行)
├── image_gen_registry.py      # 图像注册表 (129行)
├── video_gen_provider.py      # 视频生成 Provider (247行)
├── video_gen_registry.py      # 视频注册表 (94行)
│
├── background_review.py       # 后台技能/记忆审查 (676行)
├── skill_bundles.py           # 技能包 (336行)
├── skill_preprocessing.py     # 技能预处理 (127行)
│
├── onboarding.py              # 新用户引导 (193行)
├── i18n.py                    # 国际化 (254行)
├── title_generator.py         # 会话标题生成 (157行)
├── usage_pricing.py           # 用量定价 (773行)
├── insights.py                # 使用分析 (863行)
│
├── curator.py                 # 技能策展 (1,800行)
├── curator_backup.py          # 策展备份 (589行)
│
├── copilot_acp_client.py      # Copilot ACP 客户端 (543行)
├── codex_runtime.py           # Codex 运行时 (560行)
├── google_code_assist.py      # Google Code Assist (417行)
├── google_oauth.py            # Google OAuth (1,067行)
│
├── file_safety.py             # 文件安全检查 (435行)
├── markdown_tables.py         # Markdown 表格 (244行)
├── lsp/                       # LSP 支持子目录
├── transports/                # 传输层子目录
└── secret_sources/            # 密钥来源子目录
```

---

## 3. 核心文件依赖图

```
                    run_agent.py (4,816行) ← AIAgent 薄壳
                         │
         ┌───────────────┼───────────────────┐
         ▼               ▼                   ▼
  agent_init.py   conversation_loop.py   system_prompt.py
  (初始化属性)      (核心循环 4,707行)       (提示词组装)
         │               │                   │
         ▼               ▼                   ▼
  context_compressor  memory_manager    prompt_builder.py
  (上下文压缩)         (记忆管理)         (提示词部件)
         │               │
         ▼               ▼
  context_engine.py  memory_provider.py
  (ABC 基类, 可插拔)  (ABC 基类, 可插拔)
                         │
         ┌───────────────┼───────────────────┐
         ▼               ▼                   ▼
  anthropic_adapter  codex_responses   chat_completion
  (Anthropic格式)    (OpenAI Codex)    _helpers (通用)
```

**依赖原则：**
- `agent_init.py` → 只依赖 `hermes_cli/config.py` 和 `hermes_constants.py`
- `conversation_loop.py` → 依赖 `agent_init.py` 创建好的 agent 实例
- 所有模块通过 `_ra()` 惰性引用 `run_agent`，保持测试 Patch 兼容

---

## 4. AIAgent 初始化 (agent_init.py)

### 4.1 Forwarder 模式

```python
# run_agent.py — 薄壳
class AIAgent:
    def __init__(self, **kwargs):
        from agent.agent_init import init_agent
        init_agent(self, **kwargs)  # 真正的实现在 agent/agent_init.py

# agent/agent_init.py — 真正实现
def init_agent(agent, ...):
    # ~1,400行的属性初始化逻辑
    agent.model = resolved_model
    agent.provider = resolved_provider
    agent.base_url = resolved_base_url
    agent.api_key = resolved_api_key
    agent.max_iterations = max_iterations
    # ... 60+ 个参数
```

### 4.2 初始化流程（简化）

```
1. 解析模型/Provider
   ├─ 从 config.yaml / CLI 参数 / env var 三级取值
   ├─ 自动检测 Provider (API key → provider mapping)
   └─ 凭证池轮换 (credential_pool.py)

2. 初始化工具系统
   ├─ 加载工具定义 (toolsets.py)
   ├─ 注册模型适配器 (anthropic/codex/bedrock/gemini)
   └─ 构建工具 Schema 列表

3. 初始化上下文引擎
   ├─ 默认: ContextCompressor (压缩器)
   └─ 可插件替换: LCM 等

4. 初始化记忆系统
   ├─ MemoryManager 组建
   ├─ Builtin Provider (内置文件存储)
   └─ External Provider (Honcho/Mem0 等)

5. 初始化运行时设施
   ├─ 事件循环 (持久化, 每线程)
   ├─ 速率限制跟踪器
   ├─ 工具护栏 (ToolGuardrailController)
   ├─ 思考内容擦除器 (StreamingThinkScrubber)
   └─ 上下文擦除器 (StreamingContextScrubber)

6. 初始化迭代预算
   └─ IterationBudget(max_iterations)
```

### 4.3 Provider 自动检测

```python
# 根据可用的 API Key 自动选择 Provider
_PROVIDER_DETECTION_ORDER = [
    "openrouter",   # OPENROUTER_API_KEY
    "anthropic",    # ANTHROPIC_API_KEY
    "openai",       # OPENAI_API_KEY
    "deepseek",     # DEEPSEEK_API_KEY
    "google",       # GOOGLE_API_KEY
    ...
]
```

---

## 5. 核心对话循环 (conversation_loop.py)

### 5.1 函数签名

```python
def run_conversation(
    agent,                              # AIAgent 实例 (状态载体)
    user_message: str,                  # 用户消息
    system_message: str = None,         # 自定义系统提示词
    conversation_history: list = None,  # 历史对话
    task_id: str = None,               # 任务 ID
    stream_callback: callable = None,   # 流式回调
    persist_user_message: str = None,   # 持久化用的干净消息
) -> Dict[str, Any]:
```

### 5.2 完整的回合生命周期

```
┌────────────────────────────────────────────────┐
│ 1. 前置准备 (Pre-turn Setup)                     │
│    ├─ 安装安全 stdio (防断管)                      │
│    ├─ 会话 DB 连接                                │
│    ├─ 运行时配置注入                               │
│    ├─ 日志上下文设置                               │
│    ├─ 技能写入溯源标记                             │
│    ├─ Unicode 代理字符清洗                         │
│    ├─ 迭代计数器重置                               │
│    ├─ TCP 连接健康检查                             │
│    └─ 迭代预算重置                                │
├────────────────────────────────────────────────┤
│ 2. 会话恢复 (Session Hydration)                   │
│    ├─ 恢复缓存的系统提示词 (DB 读取)                │
│    ├─ 恢复 TODO 状态 (从历史解析)                  │
│    ├─ 恢复 Memory Nudge 计数                      │
│    └─ 恢复 User Turn 计数                         │
├────────────────────────────────────────────────┤
│ 3. 消息组装 (Message Assembly)                    │
│    ├─ 构建/加载系统提示词                          │
│    ├─ 预检上下文压缩 (切换小模型时)                │
│    ├─ 注入记忆上下文 (memory.prefetch)             │
│    └─ 添加用户消息到 messages 列表                 │
├────────────────────────────────────────────────┤
│ 4. 主循环 (Main Loop) ← 最多 90 次迭代            │
│    ├─ 中断检查 (_interrupt_requested)             │
│    ├─ 预算消费 (iteration_budget.consume)         │
│    ├─ /steer 排空 (预 API 注入)                    │
│    ├─ 消息清洗 (Sanitize)                         │
│    ├─ API 调用 (带重试、回退)                     │
│    │   ├─ 成功: 解析响应                          │
│    │   ├─ 失败: 错误分类 → 退避重试               │
│    │   └─ 回退模型: 主模型失败→备用模型           │
│    ├─ 响应处理                                   │
│    │   ├─ 工具调用 → 派发执行 → 结果回填          │
│    │   └─ 文本回复 → final_response = content    │
│    └─ 上下文压缩检查 (每轮后)                     │
├────────────────────────────────────────────────┤
│ 5. 后处理 (Post-turn)                            │
│    ├─ 记忆同步 (memory.sync_all)                  │
│    ├─ 记忆/技能后台审查 (Background Review)        │
│    ├─ 系统提示词回存 DB                            │
│    ├─ TODO 状态回存 DB                            │
│    ├─ 会话元数据更新                               │
│    └─ 返回结果 Dict                               │
└────────────────────────────────────────────────┘
```

### 5.3 主循环伪代码

```python
while (api_call_count < max_iterations AND budget_remaining > 0) OR grace_call:
    # 1. 中断检查
    if agent._interrupt_requested:
        break

    # 2. 预算消费
    api_call_count += 1
    if not grace_call:
        agent.iteration_budget.consume()

    # 3. 消息准备
    api_messages = sanitize_messages(messages)
    api_messages = inject_ephemeral_context(api_messages)
    api_messages[0] = {"role": "system", "content": system_prompt}

    # 4. API 调用 (带重试)
    for retry in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=api_messages,
                tools=tool_schemas,
                ...
            )
            break  # 成功
        except APIError as e:
            if is_transient(e):
                time.sleep(jittered_backoff(retry))
                continue
            raise

    # 5. 响应处理
    if has_tool_calls(response):
        for tool_call in response.tool_calls:
            # 安全检查 (Tirith)
            if agent._tool_guardrails.evaluate(tool_call) == BLOCK:
                result = "Blocked by guardrail"
            else:
                result = handle_function_call(name, args, task_id)
            messages.append({"role": "tool", "content": result, ...})
    else:
        final_response = response.content
        break  # 循环结束

# 返回结果
return {
    "final_response": final_response,
    "messages": messages,
    "api_call_count": api_call_count,
    ...
}
```

### 5.4 错误处理层次

```
API 调用失败
    ├─ 瞬态错误 (429/503) → 退避重试 (最多3次)
    ├─ 上下文超限 (400 context_length) → 触发压缩 → 重试
    ├─ 内容过滤 (400 content_filter) → 标记为失败
    ├─ 计费用尽 (402/429 billing) → 友好提示 → 终止
    ├─ 无效 JSON (tool_call 参数) → 修复后重试 (最多3次)
    ├─ 空回复 (empty content) → 重试 (最多3次)
    ├─ 不完整临时区 (incomplete scratchpad) → 重试
    └─ 全部失败 → 回退模型 (fallback_model)
```

### 5.5 回退模型机制

```
主模型调用
    ├─ 成功 → 继续
    └─ 失败 (连续 N 次)
        └─ 激活回退模型
            ├─ 本回合用回退模型完成
            └─ 下回合自动恢复主模型
```

---

## 6. 系统提示词构建 (system_prompt.py + prompt_builder.py)

### 6.1 三层结构

```
┌───────────────────────────────────────┐
│  STABLE (稳定层 — 不变的东西)           │
│  ├─ Agent 身份 (SOUL.md)              │
│  ├─ 工具使用指导                       │
│  ├─ 技能索引 (可用技能列表)             │
│  ├─ 环境提示 (OS/Shell/CWD)           │
│  ├─ 平台提示 (CLI/Gateway/TUI)         │
│  ├─ 模型家族操作指导                   │
│  └─ 专项指导 (Memory/Kanban/Session)   │
├───────────────────────────────────────┤
│  CONTEXT (上下文层 — 项目相关)          │
│  ├─ 调用者提供的 system_message        │
│  └─ 上下文文件 (AGENTS.md/.cursorrules) │
│      └─ 安全检查: 注入扫描              │
├───────────────────────────────────────┤
│  VOLATILE (挥发层 — 每会话变化)         │
│  ├─ 记忆快照 (MEMORY.md)              │
│  ├─ 用户档案 (USER.md)                │
│  ├─ 外部记忆 Provider 块              │
│  └─ 时间戳/会话/模型行                 │
└───────────────────────────────────────┘
```

### 6.2 为什么分三层？

- **Stable:** 不变 → 上游 Provider 可以缓存（Anthropic 前缀缓存命中）
- **Context:** 项目切换时变化 → 中间层
- **Volatile:** 每次会话/每次更新记忆时变化 → 最底层

**缓存策略：** 系统提示词在整个会话期间缓存不变，只有上下文压缩事件才会触发重建。如果重建，会从磁盘重新加载记忆确保最新。

### 6.3 提示词缓存恢复

```python
# Gateway 每次消息创建新 AIAgent → 必须从 DB 恢复系统提示词
# 否则每次重建导致 Anthropic 前缀缓存 MISS

def _restore_or_build_system_prompt(agent, system_message, conversation_history):
    if conversation_history and agent._session_db:
        stored_prompt = agent._session_db.get_session(session_id)["system_prompt"]
        if stored_prompt:  # "present"
            agent._cached_system_prompt = stored_prompt  # 复用
            return
        elif stored_prompt is None:  # "null" — 遗留会话
            logger.warning("重建，前缀缓存将 MISS")
        elif stored_prompt == "":   # "empty" — 持久化bug
            logger.warning("重建，前缀缓存将 MISS")

    # 首次运行或恢复失败 — 从头构建
    agent._cached_system_prompt = agent._build_system_prompt(system_message)
```

---

## 7. 上下文压缩 (context_compressor.py)

### 7.1 触发条件

```
压缩阈值 = context_length × threshold_percent (默认 75%)

触发时机:
  1. 主循环中: 每轮 API 调用后检查
  2. 预检: 循环开始前检查 (切换小模型时)
  3. 手动: /compress 斜杠命令
```

### 7.2 压缩策略

```
┌─────────────────────────────────────────────┐
│            原始消息列表                       │
│  [sys] [user][asst]...[user][asst]...[user]  │
│   ▲                            ▲         ▲  │
│   保护头 (3条)               压缩中间    保护尾(6条) │
│   (始终原样保留)            (LLM摘要)  (始终原样保留) │
└─────────────────────────────────────────────┘

压缩结果:
  [sys] [head...] [COMPACTION SUMMARY] [tail...]
```

### 7.3 摘要结构

```markdown
[CONTEXT COMPACTION — REFERENCE ONLY]

## Active Task
(当前正在做什么)

## In Progress
(进行中的子任务)

## Completed
(已完成的工作 + 产出)

## Pending User Asks
(用户未回复的问题)

## Key Context
(重要发现的上下文)

## Remaining Work
(尚未开始的工作)
```

**关键安全设计：** 摘要前缀明确规定"这只是背景参考，不是活跃指令。最新用户消息 WIN"——防止压缩后的陈旧指令劫持新回合。

### 7.4 迭代式压缩

```python
# 支持多次压缩，保留信息不丢失
# 第一次压缩: 20轮 → 摘要A
# 第二次压缩: 摘要A + 新10轮 → 摘要B (包含A的精华)
```

---

## 8. 记忆系统 (memory_manager.py + memory_provider.py)

### 8.1 架构

```
MemoryManager (编排器)
    │
    ├─ BuiltinMemoryProvider (内置, 始终注册)
    │   ├─ 文件存储: ~/.hermes/memory/
    │   ├─ MEMORY.md (~20条)
    │   └─ USER.md (~10条用户档案)
    │
    └─ External Provider (最多1个)
        ├─ Honcho
        ├─ Mem0
        └─ SuperMemory
```

### 8.2 生命周期的四个钩子

```
每个回合:
  ┌──────────────────────────────────────┐
  │ 1. build_system_prompt()            │
  │    所有 Provider 提供系统提示词块      │
  ├──────────────────────────────────────┤
  │ 2. prefetch_all(user_message)       │
  │    ← 在上一个回合的 queue_prefetch   │
  │    作为 ephemeral context 注入       │
  ├──────────────────────────────────────┤
  │ 3. sync_all(user, assistant)        │
  │    回合结束后同步到所有 Provider      │
  ├──────────────────────────────────────┤
  │ 4. queue_prefetch_all(user_message) │
  │    ← 为下一个回合准备                 │
  └──────────────────────────────────────┘
```

### 8.3 记忆工具

```python
# Memory Provider 还可以提供工具 schema
# 例如: memory(action="add", target="memory", content="...")

# MemoryManager 将 tool_name → provider 索引
# agent 调用 memory 工具时，路由到对应 Provider.handle_tool_call()
```

### 8.4 关联清洗 (StreamingContextScrubber)

```python
# 流式输出中可能包含 <memory-context> 标签
# StreamingContextScrubber 是一个状态机
# 逐 chunk 移除上下文注入，防止泄露给用户 UI

scrubber = StreamingContextScrubber()
for delta in stream:
    visible = scrubber.feed(delta)  # 过滤掉 memory-context 内容
    if visible:
        emit(visible)
```

---

## 9. Provider 适配器层

### 9.1 适配器列表

| 适配器 | 行数 | 用途 |
|--------|------|------|
| `anthropic_adapter.py` | 2,303 | Anthropic Messages API ↔ OpenAI 格式互转 |
| `codex_responses_adapter.py` | 1,260 | OpenAI Codex/Responses API |
| `bedrock_adapter.py` | 1,277 | AWS Bedrock 托管模型 |
| `gemini_native_adapter.py` | 971 | Google Gemini 原生 API |
| `gemini_cloudcode_adapter.py` | 735 | Google CloudCode |
| `chat_completion_helpers.py` | 2,457 | 通用 Chat Completion 调用 |
| `agent_runtime_helpers.py` | 2,361 | 运行时辅助 |

### 9.2 Anthropic 适配器的核心工作

```
OpenAI 消息格式 (Hermes 内部)           Anthropic Messages 格式
┌─────────────────────┐              ┌──────────────────────┐
│ role: "user"        │              │ role: "user"         │
│ content: "hello"    │   ──转换──▶  │ content: [           │
│                     │              │   {type:"text",      │
│                     │              │    text:"hello"}     │
│                     │              │ ]                    │
├─────────────────────┤              ├──────────────────────┤
│ tool_calls: [...]   │   ──转换──▶  │ content: [           │
│                     │              │   {type:"tool_use",  │
│                     │              │    id:"...",         │
│                     │              │    name:"...",       │
│                     │              │    input:{...}}      │
│                     │              │ ]                    │
├─────────────────────┤              ├──────────────────────┤
│ cache_control        │              │ 自动添加              │
│ (前缀缓存标记)       │              │ cache_control:        │
│                     │              │   {type:"ephemeral"}  │
└─────────────────────┘              └──────────────────────┘
```

---

## 10. 工具执行与安全

### 10.1 工具执行器 (tool_executor.py)

```
handle_function_call(name, args, task_id)
    │
    ├─ 查找工具 (registry)
    ├─ 安全检查 (tool_guardrails)
    │   ├─ 会话级别限制 (max_tool_calls_per_session)
    │   ├─ 工具级别限制 (rate_limit)
    │   └─ 自定义护栏规则
    ├─ Tirith 命令安全检查
    │   └─ terminal() 命令: 静态分析危险模式
    ├─ 执行 (同步 OR 异步桥接)
    │   ├─ 同步: 直接调用
    │   └─ 异步: 持久化 event_loop 上执行
    └─ 结果后处理
        └─ 密钥脱敏 (redact_secrets)
```

### 10.2 同步核心 + 异步桥接

```python
# 问题: AIAgent 循环是同步的
# 但很多 Provider SDK (httpx, AsyncOpenAI) 是异步的
# 如果每轮创建 asyncio.run() 再销毁 → "Event loop is closed"

# 解决方案: model_tools.py 维护持久化事件循环

import threading

_event_loops: Dict[int, asyncio.AbstractEventLoop] = {}

def _get_or_create_event_loop():
    thread_id = threading.get_ident()
    if thread_id not in _event_loops:
        loop = asyncio.new_event_loop()
        _event_loops[thread_id] = loop
    return _event_loops[thread_id]

def execute_async_tool(coro):
    loop = _get_or_create_event_loop()
    return loop.run_until_complete(coro)
```

### 10.3 工具护栏 (tool_guardrails.py)

```python
class ToolCallGuardrailController:
    def evaluate(self, tool_call) -> ToolGuardrailDecision:
        # 1. 会话级限制 (所有工具累计调用次数)
        if self.session_total >= max_tool_calls_per_session:
            return BLOCK("session_call_limit_exceeded")

        # 2. 每工具速率限制
        if self.per_tool_count[tool_name] >= rate_limit:
            return BLOCK("tool_rate_limit_exceeded")

        # 3. 自定义规则 (可配置)
        for rule in self.custom_rules:
            if rule.matches(tool_call) and rule.action == BLOCK:
                return BLOCK(rule.reason)

        return ALLOW
```

---

## 11. 关键技术细节

### 11.1 前缀缓存策略 (Anthropic 专属)

```python
# 系统提示词在整个会话期间不变
# → Anthropic 可以缓存前缀，后续 API 调用降价 90%

# 条件:
# 1. 系统提示词必须逐字节相同
# 2. 工具定义必须逐字节相同
# 3. Cache breakpoints 必须放在同一位置

# Hermes 实现:
# - 系统提示词缓存到 agent._cached_system_prompt
# - 会话期间永不重建
# - Gateway 从 DB 加载缓存版本
```

### 11.2 消息角色交替修复

```python
# API 要求消息必须是交替的 role
# 不正确: user → user 或 tool → user (缺少 assistant)

def _repair_message_sequence(messages):
    # 扫描并修复角色交替违规
    # 合并连续的 user 消息
    # 插入空 assistant 占位符
```

### 11.3 Thinking-Only 消息过滤

```python
# 某些模型 (DeepSeek) 可能返回纯 thinking 的 assistant 消息
# Anthropic API 拒绝 "final block is thinking" 的消息

def _is_thinking_only_assistant(msg):
    # 有 reasoning 但没有 text content 和 tool_calls
    # → 从 API 消息中移除 (UI 保留)
```

### 11.4 上下文威胁扫描

```python
# prompt_builder.py 在加载 AGENTS.md / .cursorrules 时
# 运行威胁模式扫描 (prompt injection / promptware / C2)

def _scan_context_content(content, filename):
    findings = _scan_for_threats(content, scope="context")
    if findings:
        return f"[BLOCKED: {filename} contained potential prompt injection]"
    return content  # 安全，放行
```

### 11.5 跨模块 Patch 兼容 (_ra 模式)

```python
# 问题: 从 run_agent.py 提取代码到 agent/ 子模块后
# 已有测试 patch("run_agent.handle_function_call", ...) 失效

# 解决方案: 惰性引用
def _ra():
    import run_agent
    return run_agent

# 子模块中的代码使用 _ra().handle_function_call
# → 测试的 mock.patch("run_agent.handle_function_call") 仍然生效
```

---

## 12. 设计要点总结

| # | 设计要旨 | 说明 |
|---|----------|------|
| 1 | **Forwarder 薄壳** | `run_agent.py` 只是入口，所有逻辑在 `agent/` 子模块 |
| 2 | **系统提示词三段式** | Stable + Context + Volatile，支持前缀缓存 |
| 3 | **DB 持久化的系统提示词** | Gateway 每次新 Agent 从 DB 恢复，不重建 |
| 4 | **迭代预算 + 恩惠调用** | 90 次上限 + 1 次额外机会 |
| 5 | **同步主循环** | 但工具可以是异步的（持久化事件循环桥接） |
| 6 | **上下文压缩** | 自动触发，LLM 摘要，保护头尾 |
| 7 | **记忆 Manager + Provider** | 内置 + 最多 1 个外部 Provider |
| 8 | **错误分类 + 退避重试** | 瞬态/上下文超限/内容过滤 分别处理 |
| 9 | **回退模型** | 主模型失败 → 备用模型接管 |
| 10 | **/_ra()_ 惰性引用** | 保持测试 Patch 向后兼容 |
| 11 | **消息清洗 + 修复** | 自动修复格式问题，减少 API 报错 |
| 12 | **威胁扫描** | 上下文文件加载前做注入检测 |
| 13 | **线程安全的持久化状态** | Event Loop / Scrubber 按线程隔离 |
| 14 | **可插拔上下文引擎** | ContextEngine ABC，第三方可替换压缩算法 |

---

## 附录：关键函数快速索引

| 函数 | 位置 | 职责 |
|------|------|------|
| `init_agent()` | `agent_init.py` | AIAgent 初始化 |
| `run_conversation()` | `conversation_loop.py:351` | 核心对话循环 |
| `_restore_or_build_system_prompt()` | `conversation_loop.py:218` | 系统提示词恢复 |
| `build_system_prompt()` | `system_prompt.py:61` | 提示词组装 |
| `build_system_prompt_parts()` | `system_prompt.py` | 三层结构生成 |
| `compress()` | `context_compressor.py` | 上下文压缩 |
| `prefetch_all()` | `memory_manager.py:339` | 记忆预取 |
| `sync_all()` | `memory_manager.py:383` | 记忆同步 |
| `_ra()` | 多个文件 | run_agent 惰性引用 |
