# OpenCode vs Hermes — Agent 核心层架构对比分析

> **分析日期：** 2026-06-02  
> **OpenCode 路径：** `F:\agenttool\opencode-old`（Go 实现）  
> **Hermes 路径：** `/mnt/f/agenttool/hermes`（Python 实现）  

---

## 目录

- [1. 快速概览](#1-快速概览)
- [2. 项目结构对比](#2-项目结构对比)
- [3. 核心 Agent 架构对比](#3-核心-agent-架构对比)
- [4. 主循环对比](#4-主循环对比)
- [5. 工具系统对比](#5-工具系统对比)
- [6. 提示词构建对比](#6-提示词构建对比)
- [7. 上下文管理对比](#7-上下文管理对比)
- [8. 多 Agent 对比](#8-多-agent-对比)
- [9. Provider 层对比](#9-provider-层对比)
- [10. 核心差异总结](#10-核心差异总结)
- [11. 设计哲学对比](#11-设计哲学对比)
- [12. 各有所长](#12-各有所长)

---

## 1. 快速概览

| 维度 | OpenCode | Hermes |
|------|----------|--------|
| **语言** | Go | Python |
| **定位** | CLI 编码助手 | 通用 AI Agent 框架 |
| **Agent 接口** | `agent.Service` (Go interface) | `AIAgent` (Python class) |
| **核心文件** | `agent.go` (758行) | `conversation_loop.py` (4,707行) |
| **设计风格** | 接口驱动、Channel 事件流 | Forwarder 模式、模块化 |
| **用户界面** | TUI (Bubble Tea) | CLI + TUI + 20+ 消息平台 |
| **代码量** | 核心 ~2000行 | 核心 ~20000行 |

---

## 2. 项目结构对比

### OpenCode (Go)
```
opencode-old/
├── main.go                    # 入口
├── cmd/root.go                # CLI 命令
├── internal/
│   ├── app/app.go             # 应用编排 (186行)
│   ├── llm/
│   │   ├── agent/
│   │   │   ├── agent.go       # 核心 Agent (758行)
│   │   │   ├── agent-tool.go  # 子Agent工具 (109行)
│   │   │   ├── tools.go       # 工具注册 (51行)
│   │   │   └── mcp-tools.go   # MCP工具 (201行)
│   │   ├── prompt/
│   │   │   ├── prompt.go      # 提示词分发 (137行)
│   │   │   ├── coder.go       # Coder提示词 (222行)
│   │   │   ├── task.go        # Task提示词
│   │   │   ├── title.go       # 标题生成提示词
│   │   │   └── summarizer.go  # 摘要提示词 (16行)
│   │   ├── provider/
│   │   │   ├── provider.go    # Provider接口 (247行)
│   │   │   ├── anthropic.go
│   │   │   ├── openai.go
│   │   │   ├── gemini.go
│   │   │   └── ...
│   │   ├── tools/
│   │   │   ├── tools.go       # BaseTool接口 (84行)
│   │   │   ├── bash.go, edit.go, view.go, ...
│   │   │   └── shell/shell.go
│   │   └── models/            # 模型定义
│   ├── session/               # 会话管理
│   ├── message/               # 消息数据模型
│   ├── config/                # 配置
│   └── tui/                   # Bubble Tea TUI
```

### Hermes (Python)
```
hermes/
├── run_agent.py               # AIAgent 薄壳 (4,816行)
├── cli.py                     # CLI 编排 (15,744行)
├── model_tools.py             # 工具调度 (1,067行)
├── toolsets.py                # 工具集定义 (882行)
├── agent/
│   ├── agent_init.py          # 初始化 (1,657行)
│   ├── conversation_loop.py   # 核心循环 (4,707行)
│   ├── system_prompt.py       # 提示词组装 (407行)
│   ├── prompt_builder.py      # 提示词部件 (1,507行)
│   ├── context_compressor.py  # 上下文压缩 (2,078行)
│   ├── memory_manager.py      # 记忆管理 (653行)
│   ├── memory_provider.py     # 记忆Provider (336行)
│   ├── anthropic_adapter.py   # Anthropic适配 (2,303行)
│   ├── codex_responses_adapter.py
│   └── ... 108个 .py 文件
├── tools/
│   ├── registry.py            # 工具注册表 (589行)
│   └── *.py                   # ~82个工具文件
└── gateway/
    ├── run.py                 # 多平台网关 (19,556行)
    └── platforms/             # 20+平台适配器
```

---

## 3. 核心 Agent 架构对比

### OpenCode：接口驱动的 Service 模式

```go
// 核心接口
type Service interface {
    pubsub.Subscriber[AgentEvent]
    Model() models.Model
    Run(ctx context.Context, sessionID string, content string, attachments ...message.Attachment) (<-chan AgentEvent, error)
    Cancel(sessionID string)
    IsSessionBusy(sessionID string) bool
    IsBusy() bool
    Update(agentName config.AgentName, modelID models.ModelID) (models.Model, error)
    Summarize(ctx context.Context, sessionID string) error
}

// 内部实现结构体 — 极简
type agent struct {
    *pubsub.Broker[AgentEvent]          // 事件发布/订阅
    sessions  session.Service           // 会话存储
    messages  message.Service           // 消息存储
    tools     []tools.BaseTool          // 工具列表
    provider  provider.Provider         // LLM Provider
    titleProvider     provider.Provider // 标题生成
    summarizeProvider provider.Provider // 摘要生成
    activeRequests    sync.Map          // 活跃请求 (取消控制)
}
```

**特点：**
- 6 个字段，依赖注入清晰
- Go 接口 + 结构体 = 编译期安全
- `sync.Map` 管理并发请求和取消

### Hermes：Forwarder 模式 + 模块拆分

```python
# run_agent.py — 薄壳
class AIAgent:
    def __init__(self, **60+ params):
        from agent.agent_init import init_agent
        init_agent(self, **params)  # 实际实现

    def run_conversation(self, ...):
        from agent.conversation_loop import run_conversation
        return run_conversation(self, ...)

    def _build_system_prompt(self, ...):
        from agent.system_prompt import build_system_prompt
        return build_system_prompt(self, ...)
```

```python
# 实际实现分布在 agent/ 模块中
# agent_init.py: ~1,400行初始化逻辑
# conversation_loop.py: ~4,700行核心循环
# system_prompt.py: 三层提示词组装
```

**特点：**
- 60+ 个初始化参数
- Forwarder 将逻辑拆分到 agent/ 子模块
- `_ra()` 惰性引用保持测试兼容
- 一行 `self` 贯通所有状态

---

## 4. 主循环对比

### OpenCode: `processGeneration()`

```go
// agent.go:233
func (a *agent) processGeneration(ctx context.Context, sessionID, content string, attachmentParts []message.ContentPart) AgentEvent {
    // 1. 加载历史消息
    msgs, _ := a.messages.List(ctx, sessionID)
    
    // 2. 首条消息 → 异步生成标题
    if len(msgs) == 0 {
        go a.generateTitle(...)
    }
    
    // 3. 处理摘要（如果有）
    if session.SummaryMessageID != "" {
        msgs = msgs[summaryMsgIndex:]  // 截断到摘要位置
    }
    
    // 4. 添加用户消息
    userMsg := a.createUserMessage(...)
    msgHistory := append(msgs, userMsg)
    
    // 5. 主循环 — for {} 直到文本回复
    for {
        // 取消检查
        select {
        case <-ctx.Done():
            return a.err(ctx.Err())
        default:
        }
        
        // API 调用 + 流式事件处理
        agentMessage, toolResults, err := a.streamAndHandleEvents(ctx, sessionID, msgHistory)
        
        // 工具调用 → 结果回填 → 继续循环
        if agentMessage.FinishReason() == message.FinishReasonToolUse && toolResults != nil {
            msgHistory = append(msgHistory, agentMessage, *toolResults)
            continue
        }
        
        // 文本回复 → 结束
        return AgentEvent{
            Type:    AgentEventTypeResponse,
            Message: agentMessage,
            Done:    true,
        }
    }
}
```

**循环控制:**
- `ctx.Done()` — Go Context 取消
- 无条件循环 (`for {}`)
- 通过 Channel 接收事件流

### Hermes: `run_conversation()`

```python
# conversation_loop.py:796
while (api_call_count < agent.max_iterations AND budget_remaining > 0) OR grace_call:
    # 1. 中断检查
    if agent._interrupt_requested:
        break
    
    # 2. 预算消费
    api_call_count += 1
    agent.iteration_budget.consume()
    
    # 3. /steer 排空
    _pre_api_steer = agent._drain_pending_steer()
    
    # 4. 消息清洗
    api_messages = sanitize(messages)
    
    # 5. API 调用 (带重试、回退)
    response = _interruptible_api_call(agent, api_messages)
    
    # 6. 处理响应
    if response.tool_calls:
        for tc in response.tool_calls:
            result = handle_function_call(tc.name, tc.args)
            messages.append(tool_result_message(result))
        continue
    else:
        final_response = response.content
        break
```

**循环控制:**
- `max_iterations` (默认 90) + `iteration_budget` 双重限制
- `_budget_grace_call` — 预算耗尽但再给一次机会
- `_interrupt_requested` — 用户新消息触发中断

### 对比总结

| 维度 | OpenCode | Hermes |
|------|----------|--------|
| 循环边界 | `for {}` 无上限 + ctx 取消 | 90次迭代 + 预算 + 中断标志 |
| 取消机制 | Go Context (ctx.Done) | `_interrupt_requested` 标志 |
| 流式处理 | Channel (`<-chan ProviderEvent`) | 可选 stream_callback |
| 错误重试 | Provider 层 `maxRetries=8` | 多层重试 (3次/类型) + 回退模型 |
| 消息持久化 | 每事件实时 DB 写入 | 回合结束后批量写入 |

---

## 5. 工具系统对比

### OpenCode：接口驱动 + 手动注册

```go
// 工具接口
type BaseTool interface {
    Info() ToolInfo              // 返回名称、描述、参数Schema
    Run(ctx context.Context, params ToolCall) (ToolResponse, error)  // 执行
}

// 手动组装工具列表
func CoderAgentTools(...) []tools.BaseTool {
    return []tools.BaseTool{
        tools.NewBashTool(permissions),
        tools.NewEditTool(lspClients, permissions, history),
        tools.NewGlobTool(),
        tools.NewGrepTool(),
        tools.NewViewTool(lspClients),
        tools.NewPatchTool(lspClients, permissions, history),
        tools.NewWriteTool(lspClients, permissions, history),
        NewAgentTool(sessions, messages, lspClients),  // 子Agent
        GetMcpTools(ctx, permissions)...,               // MCP工具
    }
}

// 工具执行 (agent.go:367-419)
for _, availableTool := range a.tools {
    if availableTool.Info().Name == toolCall.Name {
        tool = availableTool
        break
    }
}
toolResult, toolErr := tool.Run(ctx, tools.ToolCall{...})
```

**特点:**
- 极其简洁：一个接口，两个方法
- 工具列表手工组装（`CoderAgentTools()` 函数）
- 子 Agent 也是工具（`NewAgentTool`）
- MCP 工具统一包装成 `mcpTool` 结构体

### Hermes：AST 自发现 + 两层门控

```python
# 工具注册 (tools/*.py)
from tools.registry import registry

registry.register(
    name="web_search",
    toolset="web",
    schema={...},
    handler=lambda args, **kw: do_search(args["query"]),
    check_fn=check_requirements,
    requires_env=["SERPER_API_KEY"],
)

# 自动发现 (tools/registry.py)
# AST 扫描 tools/*.py 找到 register() 调用
# → 无需手动 import 或列表

# 门控 (toolsets.py)
_HERMES_CORE_TOOLS = [57个工具名]
# → 只有列表里的工具对 Agent 可见
```

**特点:**
- 工具文件只需调用 `register()` — 自动发现
- 两层控制：AST 发现 + 白名单门控
- 工具按 toolset 分组（web/terminal/file/safe/...）
- `check_fn` 检查环境是否满足运行条件
- 异步工具通过持久化 Event Loop 桥接

### 对比总结

| 维度 | OpenCode | Hermes |
|------|----------|--------|
| 发现机制 | 手动函数组装 | AST 扫描 + 自动导入 |
| 工具数量 | ~12 个内置 + MCP | 57 个核心 + 可选 |
| 安全模型 | Permission Service | Toolset 白名单 + Tirith |
| 异步支持 | 不需要 (Go 天然并发) | 持久化 Event Loop 桥接 |
| 子 Agent | `agentTool` (独立工具) | `delegate_task` + kanban |

---

## 6. 提示词构建对比

### OpenCode：静态常量 + Provider 分支

```go
// prompt/coder.go
func CoderPrompt(provider models.ModelProvider) string {
    basePrompt := baseAnthropicCoderPrompt       // 静态常量
    switch provider {
    case models.ProviderOpenAI:
        basePrompt = baseOpenAICoderPrompt       // 另一个静态常量
    }
    envInfo := getEnvironmentInfo()              // OS/Shell/CWD
    return fmt.Sprintf("%s\n%s\n%s", basePrompt, envInfo, lspInformation())
}

// 多个 Agent 各有独立 Prompt:
// - CoderPrompt (222行常量)
// - TaskPrompt
// - TitlePrompt
// - SummarizerPrompt (16行)
```

**特点:**
- 每个 Agent 类型有独立的静态 Prompt 常量
- Per-Provider 分支切换不同 Prompt
- 项目上下文文件 (AGENTS.md/CLAUDE.md) 用 `getContextFromPaths()` 注入
- 环境信息简洁：OS/Shell/CWD/Date/LSP

### Hermes：三段式动态组装

```python
# system_prompt.py
def build_system_prompt_parts(agent):
    return {
        "stable":    # 身份 + 工具指导 + 技能索引 + 环境提示 + 模型指导
        "context":   # system_message + AGENTS.md/.cursorrules（含威胁扫描）
        "volatile":  # 记忆快照 + 用户档案 + 记忆Provider块 + 时间戳
    }

# prompt_builder.py — 每个部分单独构建函数
# DEFAULT_AGENT_IDENTITY     ← SOUL.md 或 默认身份
# build_environment_hints()  ← OS/Shell/CWD/WSL检测
# build_skills_system_prompt() ← 可用技能列表
# build_context_files_prompt() ← AGENTS.md 加载 + 威胁扫描
```

**三段式设计逻辑:**
- **Stable:** 不变 → Provider 前缀缓存命中（Anthropic 降价 90%）
- **Context:** 项目切换时变化
- **Volatile:** 每次会话/记忆更新时变化

**特点:**
- 极长的提示词（包含技能列表、记忆、项目文件）
- 前缀缓存感知设计
- 威胁扫描防御 Prompt Injection
- 记忆内容自动注入
- Gateway 通过 DB 恢复缓存版本

### 对比总结

| 维度 | OpenCode | Hermes |
|------|----------|--------|
| 提示词长度 | ~2,500 字符 | ~15,000+ 字符 |
| 构造方式 | 静态常量 | 动态函数组装 |
| 记忆注入 | 无 | 内置Provider + 外部Provider |
| 技能注入 | 无 | Skills 系统（技能发现+索引） |
| 项目上下文 | Context Paths | AGENTS.md + .cursorrules |
| 安全检查 | 无 | 威胁模式扫描 |
| 缓存设计 | 无特殊设计 | Anthropic前缀缓存感知 |

---

## 7. 上下文管理对比

### OpenCode：摘要式压缩

```go
// agent.go:255-267
if session.SummaryMessageID != "" {
    // 找到摘要消息位置
    // 丢弃摘要之前的所有消息
    msgs = msgs[summaryMsgIndex:]
    msgs[0].Role = message.User  // 摘要设为用户角色
}

// Summarize() 方法
func (a *agent) Summarize(ctx context.Context, sessionID string) error {
    // 使用 Summarizer Agent (独立Agent类型)
    // 异步生成摘要
    // 存储 SummaryMessageID 到 session
}
```

**特点:**
- 独立 Summarizer Agent（专门的小模型）
- 摘要后截断历史（只保留摘要+后续）
- 摘要消息标注为 `Role: User`

### Hermes：结构化 LLM 压缩

```python
# context_compressor.py
class ContextCompressor:
    threshold_percent = 0.75      # 75% 触发
    protect_first_n = 3           # 保护头部3条
    protect_last_n = 6            # 保护尾部6条
    
    def compress(self, messages):
        # 1. 用辅助模型生成结构化摘要
        summary = call_auxiliary_llm(compression_prompt.format(middle))
        
        # 2. 摘要结构：
        #    ## Active Task / ## In Progress / ## Completed
        #    ## Pending User Asks / ## Key Context / ## Remaining Work
        
        # 3. 组合: [head...] + [SUMMARY] + [tail...]
        return compact_messages
    
    # 迭代压缩: 支持多次压缩保留信息
```

**特点:**
- 固定阈值触发 + 预检（切换小模型时）
- 结构化摘要模板，防止陈旧指令劫持
- 迭代式压缩（第二次压缩保留第一次的精华）
- 工具输出预剪枝（LLM摘要前先去掉冗余）

### 对比总结

| 维度 | OpenCode | Hermes |
|------|----------|--------|
| 触发方式 | 手动/自动？ | 阈值自动触发 (75%) |
| 摘要方法 | 独立 Agent 生成 | 辅助 LLM + 结构化模板 |
| 压缩粒度 | 丢弃旧消息只保留摘要 | 保护头尾 + 摘要中间 |
| 防劫持 | 摘要标注为 User 角色 | SUMMARY_PREFIX 显式声明 |
| 迭代支持 | 否 | 是（摘要累积） |

---

## 8. 多 Agent 对比

### OpenCode：Agent 类型分离

```go
// 5种 Agent 类型，各有独立 Prompt 和工具
config.AgentCoder       // 主编码 Agent (全部工具)
config.AgentTask        // 子任务 Agent (只读工具: Glob/Grep/LS/View)
config.AgentTitle       // 标题生成 Agent (无工具)
config.AgentSummarizer  // 摘要生成 Agent (无工具)

// 子 Agent 嵌套
// agent-tool.go: NewAgentTool → 创建 AgentTask → Run
func (b *agentTool) Run(ctx context.Context, call tools.ToolCall) (tools.ToolResponse, error) {
    agent, _ := NewAgent(config.AgentTask, ...)
    session, _ := b.sessions.CreateTaskSession(ctx, ...)
    done, _ := agent.Run(ctx, session.ID, params.Prompt)
    result := <-done  // 阻塞等待子Agent完成
    return tools.NewTextResponse(result.Message.Content().String()), nil
}
```

**特点:**
- Agent 类型 = 工具集 + Prompt 组合
- Task Agent 只有只读工具
- 子 Agent 通过 `agentTool` 工具创建
- 每个子 Agent 有独立 Session
- 子 Agent 的费用累加到父 Session

### Hermes：delegate_task + Kanban + Cron

```python
# delegate_task — 同步子Agent
delegate_task(goal="分析bug", context="...", toolsets=["terminal", "file"])
# → 创建隔离上下文 + 独立终端会话
# → 父Agent阻塞等待子Agent摘要

# Kanban — 多Profile协作
# → SQLite 任务板
# → 不同Profile Worker领取任务
# → 异步执行

# Cron — 定时自主Agent
# → 定期触发Agent执行特定任务
# → 完全独立于当前会话
```

**特点:**
- 三层多Agent：delegate_task(同步) + Kanban(异步多Profile) + Cron(定时)
- delegate_task 支持批量并行（最多3个同时）
- 子Agent有独立工具集和终端会话
- 迭代预算和中断机制保护父Agent

### 对比总结

| 维度 | OpenCode | Hermes |
|------|----------|--------|
| Agent 类型 | 4种（Coder/Task/Title/Summarizer） | 运行时配置（toolsets） |
| 子Agent | agentTool (阻塞等待) | delegate_task + Kanban + Cron |
| 隔离级别 | 独立Session | 独立Context + 终端 + 工具集 |
| 并行 | 单个子Agent | 批量并行（最多3） |
| 持久化 | 无 | Kanban SQLite / Cron调度器 |

---

## 9. Provider 层对比

### OpenCode：接口 + Channel 事件流

```go
type Provider interface {
    SendMessages(ctx context.Context, messages []message.Message, tools []tools.BaseTool) (*ProviderResponse, error)
    StreamResponse(ctx context.Context, messages []message.Message, tools []tools.BaseTool) <-chan ProviderEvent
    Model() models.Model
}

// 事件类型（10种）
const (
    EventContentStart, EventToolUseStart, EventToolUseDelta,
    EventToolUseStop, EventContentDelta, EventThinkingDelta,
    EventContentStop, EventComplete, EventError, EventWarning
)
```

**实现：**
- `internal/llm/provider/anthropic.go`
- `internal/llm/provider/openai.go`
- `internal/llm/provider/gemini.go`
- `internal/llm/provider/copilot.go`
- ... 8个 Provider

### Hermes：Forwarder + Adapter 模式

```python
# 没有统一 Provider 接口
# 不同 API 模式用不同 Adapter:
# - anthropic_adapter.py    → Anthropic Messages API
# - codex_responses_adapter.py → OpenAI Codex
# - chat_completion_helpers.py → 通用 Chat Completion
# - bedrock_adapter.py     → AWS Bedrock
# - gemini_native_adapter.py → Google Gemini

# 调用路径 (conversation_loop.py 中)
if agent.api_mode == "anthropic_messages":
    response = agent._make_anthropic_call(api_messages)
elif agent.api_mode == "codex_responses":
    response = agent._make_codex_call(api_messages)
else:
    response = agent._make_chat_completion_call(api_messages)
```

### 对比总结

| 维度 | OpenCode | Hermes |
|------|----------|--------|
| 接口设计 | 统一 Provider 接口 | 按 API 模式分支 |
| 事件模型 | 10种事件的 Channel | 回调函数 (stream_callback) |
| 重试机制 | Provider 层 `maxRetries=8` | 分类重试 (3次/类) + 回退 |
| 支持 Provider | 8个 | 15+ 个 |

---

## 10. 核心差异总结

| # | 维度 | OpenCode | Hermes |
|---|------|----------|--------|
| 1 | **语言** | Go | Python |
| 2 | **Agent 实现** | `agent.Service` 接口 | `AIAgent` 类 (Forwarder) |
| 3 | **核心循环** | `for {}` + ctx.Done | `while` + budget + interrupt |
| 4 | **事件模型** | Channel + Pub/Sub | 同调函数 + 轮询 |
| 5 | **工具发现** | 手动函数组装 | AST 扫描 + 白名单 |
| 6 | **提示词** | 静态常量 Per-Agent | 三段式动态组装 |
| 7 | **记忆** | ❌ 无 | ✅ MemoryManager + Provider |
| 8 | **技能** | ❌ 无 | ✅ Skills 系统 |
| 9 | **压缩** | 摘要截断 | 结构化 LLM 压缩 |
| 10 | **子Agent** | agentTool | delegate_task + Kanban + Cron |
| 11 | **平台支持** | TUI only | CLI + TUI + 20+ 消息平台 |
| 12 | **安全** | Permission Service | 多层 (Tirith/Guardrail/Redact) |
| 13 | **配置** | `~/.config/opencode/` | `~/.hermes/config.yaml` |
| 14 | **扩展性** | MCP 服务器 | Plugins + MCP + Skills |

---

## 11. 设计哲学对比

### OpenCode：简约优先 (Less is More)

```
核心理念：
  ✅ 精简单文件 — agent.go 只有 758 行
  ✅ Go 接口是契约 — 编译期保证
  ✅ Channel 天然异步 — 无需手动管理线程
  ✅ 每种 Agent 专注一件事
  ✅ 无记忆 — 不储存用户信息
  ✅ 无技能 — 不积累"怎么做"

代价：
  ❌ 功能有限 — 没有多平台支持
  ❌ 无上下文感知 — 忘记谁在用
  ❌ 不能定时执行
  ❌ 不能自学习
```

### Hermes：功能完备 (Batteries Included)

```
核心理念：
  ✅ 技能自学习 — 解决问题后存为 Skill
  ✅ 跨会话记忆 — 用户偏好持久化
  ✅ 多平台统一 — 同一 Agent 多端运行
  ✅ Profile 多租户 — 工作/个人完全隔离
  ✅ 丰富工具链 — 57+ 内置工具
  ✅ 可扩展 — Plugins + MCP + Skills

代价：
  ❌ 复杂度高 — 核心 ~20,000 行
  ❌ 提示词长 — ~15,000 字符 token 成本高
  ❌ 初始化重 — 60+ 参数
  ❌ 学习曲线陡
```

---

## 12. 各有所长

### OpenCode 更适合

| 场景 | 原因 |
|------|------|
| **纯编码助手** | Bash/Edit/View/Write/Glob/Grep 够用 |
| **性能敏感** | Go 编译型，启动快，内存低 |
| **简单部署** | 单二进制，无 Python 依赖 |
| **IDE 集成** | LSP 深度整合 |
| **团队简单** | 无记忆/技能需要管理的状态 |

### Hermes 更适合

| 场景 | 原因 |
|------|------|
| **通用 AI 助手** | 不仅编码，还能研究/创作/自动化 |
| **多平台用户** | CLI + 微信 + Telegram + 飞书... |
| **长期使用** | 记忆系统 + 技能积累 = 越用越聪明 |
| **复杂工作流** | Cron + Kanban + delegate_task |
| **内容创作** | 图像/视频/语音/TTS 全栈 |
| **多身份场景** | Profile 隔离（工作 vs 个人） |

---

## 附录：代码片段速查

### OpenCode 核心循环 (<50行)

```go
for {
    select {
    case <-ctx.Done():
        return a.err(ctx.Err())
    default:
    }
    agentMessage, toolResults, err := a.streamAndHandleEvents(ctx, sessionID, msgHistory)
    if agentMessage.FinishReason() == message.FinishReasonToolUse && toolResults != nil {
        msgHistory = append(msgHistory, agentMessage, *toolResults)
        continue
    }
    return AgentEvent{Type: AgentEventTypeResponse, Message: agentMessage, Done: true}
}
```

### Hermes 核心循环 (<40行)

```python
while (api_call_count < agent.max_iterations and budget_remaining > 0) or grace_call:
    if agent._interrupt_requested:
        break
    api_call_count += 1
    agent.iteration_budget.consume()
    response = _interruptible_api_call(agent, api_messages)
    if response.tool_calls:
        for tc in response.tool_calls:
            messages.append(handle_function_call(tc.name, tc.args))
    else:
        final_response = response.content
        break
```
