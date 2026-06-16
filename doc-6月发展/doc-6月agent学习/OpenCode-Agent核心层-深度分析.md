# OpenCode Agent 核心层 — 深度分析报告

> **分析日期：** 2026-06-02  
> **代码仓库：** `F:\agenttool\opencode-old`  
> **实现语言：** Go  
> **核心文件行数：** agent.go (758行) + agent-tool.go (109行) + tools.go (51行) + mcp-tools.go (201行)  

---

## 目录

- [1. 项目概况](#1-项目概况)
- [2. 整体架构](#2-整体架构)
- [3. Agent Service 接口](#3-agent-service-接口)
- [4. Agent 结构体](#4-agent-结构体)
- [5. 核心执行流程](#5-核心执行流程)
- [6. 流式事件处理](#6-流式事件处理)
- [7. 四种 Agent 类型](#7-四种-agent-类型)
- [8. 子 Agent 委托](#8-子-agent-委托)
- [9. 工具系统](#9-工具系统)
- [10. Provider 层](#10-provider-层)
- [11. 消息数据模型](#11-消息数据模型)
- [12. 会话管理](#12-会话管理)
- [13. 权限安全模型](#13-权限安全模型)
- [14. LSP 集成](#14-lsp-集成)
- [15. Pub/Sub 事件总线](#15-pubsub-事件总线)
- [16. 上下文管理](#16-上下文管理)
- [17. 设计模式与亮点](#17-设计模式与亮点)
- [18. 局限与边界](#18-局限与边界)

---

## 1. 项目概况

**OpenCode** 是一个用 Go 语言编写的 CLI 编码助手，对标 Claude Code / Codex CLI。核心 Agent 层**极其精简**——`agent.go` 只有 758 行，所有逻辑一目了然。

| 维度 | 数据 |
|------|------|
| 语言 | Go |
| AGPL-3.0 许可证 |
| 核心 Agent 文件 | 4 个 (agent.go + agent-tool.go + tools.go + mcp-tools.go) |
| 总核心代码 | ~1,100 行 |
| 工具数量 | 13 个内置 + MCP 扩展 |
| 支持的 Provider | Anthropic / OpenAI / Gemini / Copilot / Azure / Bedrock / Groq / XAI / Local |
| 存储 | SQLite (通过 sqlc 生成查询) |
| UI | Bubble Tea TUI |
| 可扩展性 | MCP 协议 |

---

## 2. 整体架构

```
┌──────────────────────────────────────────┐
│           App (app.go: 186行)             │
│  编排层：创建Agent、LSP、启动TUI           │
└────────────────┬─────────────────────────┘
                 │
    ┌────────────┼──────────────┐
    ▼            ▼              ▼
┌────────┐ ┌──────────┐ ┌──────────────┐
│ Session│ │ Message  │ │ Permission   │
│ Service│ │ Service  │ │ Service      │
│ (156行)│ │ (281行)  │ │ (119行)      │
└───┬────┘ └────┬─────┘ └──────┬───────┘
    │           │              │
    ▼           ▼              ▼
┌─────────────────────────────────────────┐
│           Agent Service                  │
│           (agent.go: 758行)              │
│                                          │
│  ┌──────────┐  ┌──────────────────────┐ │
│  │ Provider │  │  Tools (13个内置+MCP) │ │
│  │ 9种后端  │  │  Bash/Edit/View/...  │ │
│  └──────────┘  └──────────────────────┘ │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │  Title   │  │Summarizer│  │ Task  │ │
│  │  Agent   │  │  Agent   │  │ Agent │ │
│  └──────────┘  └──────────┘  └───────┘ │
└─────────────────────────────────────────┘
```

**依赖方向：** App → Agent → {Provider, Tools} → {Session, Message} → SQLite

---

## 3. Agent Service 接口

```go
// internal/llm/agent/agent.go:48-57
type Service interface {
    pubsub.Subscriber[AgentEvent]                    // 事件订阅

    Model() models.Model                             // 当前模型信息

    Run(ctx context.Context, sessionID string,
        content string,
        attachments ...message.Attachment,
    ) (<-chan AgentEvent, error)                     // 执行对话

    Cancel(sessionID string)                         // 取消请求
    IsSessionBusy(sessionID string) bool             // 会话是否忙碌
    IsBusy() bool                                    // 是否有活跃请求

    Update(agentName config.AgentName,
        modelID models.ModelID,
    ) (models.Model, error)                          // 运行时切换模型

    Summarize(ctx context.Context,
        sessionID string,
    ) error                                         // 压缩对话历史
}
```

接口设计体现了 Go 的哲学：**极简、明确、单一职责**。8 个方法覆盖了 Agent 的全部生命周期。

---

## 4. Agent 结构体

```go
// internal/llm/agent/agent.go:59-71
type agent struct {
    *pubsub.Broker[AgentEvent]         // 嵌入事件广播器

    sessions  session.Service          // 会话 CRUD
    messages  message.Service          // 消息 CRUD

    tools     []tools.BaseTool         // 工具列表

    provider          provider.Provider   // 主力 LLM
    titleProvider     provider.Provider   // 标题生成专用
    summarizeProvider provider.Provider   // 摘要生成专用

    activeRequests    sync.Map            // 活跃请求 (取消控制)
}
```

**6 个字段 + 1 个并发控制 map**，清晰到可以背下来：

| 字段 | 作用 |
|------|------|
| `Broker` | Pub/Sub 事件广播，通知 UI 层 |
| `sessions` | 会话 CRUD，存 SQLite |
| `messages` | 消息 CRUD，存 SQLite |
| `tools` | 工具列表（Bash/Edit/View/...） |
| `provider` | 主力 Provider（调用 Claude/GPT） |
| `titleProvider` | 便宜的模型生成会话标题 |
| `summarizeProvider` | 便宜的模型压缩对话 |
| `activeRequests` | `sync.Map` 存储 `sessionID → context.CancelFunc` |

---

## 5. 核心执行流程

### 5.1 入口：`Run()`

```go
// agent.go:198 — 极简的异步入口
func (a *agent) Run(ctx context.Context, sessionID string,
    content string, attachments ...message.Attachment) (<-chan AgentEvent, error) {

    if a.IsSessionBusy(sessionID) {
        return nil, ErrSessionBusy         // 同一会话同时只有一个请求
    }

    genCtx, cancel := context.WithCancel(ctx)
    a.activeRequests.Store(sessionID, cancel)  // 注册取消函数

    events := make(chan AgentEvent)

    go func() {                             // 异步 goroutine
        defer logging.RecoverPanic(...)     // panic 恢复
        result := a.processGeneration(genCtx, sessionID, content, attachmentParts)
        a.activeRequests.Delete(sessionID)  // 清理
        cancel()
        a.Publish(pubsub.CreatedEvent, result)
        events <- result
        close(events)
    }()

    return events, nil
}
```

**关键设计：** `Run()` 立即返回 `<-chan AgentEvent`，实际工作在 goroutine 里跑。调用方从 Channel 读事件即可。

### 5.2 主循环：`processGeneration()`

```go
// agent.go:233 — 完整的主循环
func (a *agent) processGeneration(ctx, sessionID, content, attachmentParts) AgentEvent {

    // ──── 阶段 1: 加载历史 ────
    msgs, _ := a.messages.List(ctx, sessionID)

    // 首次消息 → 异步生成标题
    if len(msgs) == 0 {
        go a.generateTitle(context.Background(), sessionID, content)
    }

    // 处理摘要
    if session.SummaryMessageID != "" {
        msgs = msgs[summaryMsgIndex:]  // 截断到摘要
        msgs[0].Role = message.User    // 摘要设为 User 角色
    }

    // ──── 阶段 2: 添加用户消息 ────
    userMsg := a.createUserMessage(ctx, sessionID, content, attachmentParts)
    msgHistory := append(msgs, userMsg)

    // ──── 阶段 3: 主循环 ────
    for {
        // 取消检查
        select {
        case <-ctx.Done():
            return a.err(ctx.Err())
        default:
        }

        // API 调用 + 流式事件处理
        agentMessage, toolResults, err := a.streamAndHandleEvents(ctx, sessionID, msgHistory)

        // 工具调用 → 回填结果 → 继续
        if agentMessage.FinishReason() == FinishReasonToolUse && toolResults != nil {
            msgHistory = append(msgHistory, agentMessage, *toolResults)
            continue
        }

        // 文本回复 → 结束
        return AgentEvent{Type: "response", Message: agentMessage, Done: true}
    }
}
```

**循环特点：**
- `for {}` 无条件循环 —— 不设迭代上限，完全依赖 LLM 自行停止
- 取消通过 Go Context（`ctx.Done()`）
- 无预算、无重试（重试在 Provider 层，最多 8 次）

### 5.3 API 调用 + 事件处理：`streamAndHandleEvents()`

```go
// agent.go:322 — 流式事件处理
func (a *agent) streamAndHandleEvents(ctx, sessionID, msgHistory) (msg, *toolResults, error) {

    // 1. 启动流式请求
    eventChan := a.provider.StreamResponse(ctx, msgHistory, a.tools)

    // 2. 创建 assistant 消息（写入 DB）
    assistantMsg, _ := a.messages.Create(ctx, sessionID, CreateMessageParams{
        Role:  message.Assistant,
        Parts: []ContentPart{},
        Model: a.provider.Model().ID,
    })

    // 3. 处理每一个流式事件
    for event := range eventChan {
        a.processEvent(ctx, sessionID, &assistantMsg, event)  // 实时更新 DB
        if ctx.Err() != nil {
            a.finishMessage(ctx, &assistantMsg, FinishReasonCanceled)
            return assistantMsg, nil, ctx.Err()
        }
    }

    // 4. 执行所有工具调用
    for _, toolCall := range assistantMsg.ToolCalls() {
        select {
        case <-ctx.Done():
            // 取消后续工具
            for j := i; j < len(toolCalls); j++ {
                toolResults[j] = ToolResult{..., IsError: true}
            }
            break
        default:
            tool := findToolByName(toolCall.Name)
            result, err := tool.Run(ctx, toolCall)
            toolResults[i] = result
        }
    }

    return assistantMsg, &toolResultsMsg, nil
}
```

**亮点：**
- 流式事件实时写入 DB（每个 delta 都 Update）
- 工具调用批量执行，可以中途取消
- 非流式 Provider 用 `SendMessages` 降级

---

## 6. 流式事件处理

### 6.1 事件类型

```go
// provider/provider.go:17-28 — 10 种事件
const (
    EventContentStart  EventType = "content_start"
    EventToolUseStart  EventType = "tool_use_start"
    EventToolUseDelta  EventType = "tool_use_delta"
    EventToolUseStop   EventType = "tool_use_stop"
    EventContentDelta  EventType = "content_delta"
    EventThinkingDelta EventType = "thinking_delta"
    EventContentStop   EventType = "content_stop"
    EventComplete      EventType = "complete"
    EventError         EventType = "error"
    EventWarning       EventType = "warning"
)
```

### 6.2 事件处理函数

```go
// agent.go:445 — processEvent 实现
func (a *agent) processEvent(ctx, sessionID, assistantMsg, event) error {
    switch event.Type {
    case EventThinkingDelta:
        assistantMsg.AppendReasoningContent(event.Content)  // 追加思考
        return a.messages.Update(ctx, *assistantMsg)        // 写入 DB

    case EventContentDelta:
        assistantMsg.AppendContent(event.Content)           // 追加文本
        return a.messages.Update(ctx, *assistantMsg)        // 写入 DB

    case EventToolUseStart:
        assistantMsg.AddToolCall(*event.ToolCall)           // 记录工具调用
        return a.messages.Update(ctx, *assistantMsg)

    case EventToolUseStop:
        assistantMsg.FinishToolCall(event.ToolCall.ID)     // 标记工具调用结束
        return a.messages.Update(ctx, *assistantMsg)

    case EventComplete:
        assistantMsg.SetToolCalls(event.Response.ToolCalls)
        assistantMsg.AddFinish(event.Response.FinishReason)
        a.messages.Update(ctx, *assistantMsg)
        a.TrackUsage(ctx, sessionID, a.provider.Model(), event.Response.Usage)

    case EventError:
        if errors.Is(event.Error, context.Canceled) {
            return context.Canceled
        }
        return event.Error
    }
}
```

**Key insight：** 每个 delta 都实时写入 SQLite。即使进程崩溃，也不会丢失已流式输出的内容。

---

## 7. 四种 Agent 类型

OpenCode 不是单一 Agent，而是 **4 个独立 Agent 分工协作**：

```
┌─────────────────────────────────────────────────┐
│                 Agent 类型体系                    │
│                                                  │
│  AgentCoder      AgentTask     AgentTitle   AgentSummarizer
│  ┌──────────┐   ┌──────────┐  ┌─────────┐  ┌──────────┐
│  │ 全部工具  │   │ 只读工具  │  │ 无工具  │  │ 无工具   │
│  │ Bash      │   │ Glob     │  │         │  │          │
│  │ Edit      │   │ Grep     │  │ 标题生成 │  │ 摘要生成  │
│  │ View      │   │ LS       │  │         │  │          │
│  │ Write     │   │ View     │  │ 便宜模型 │  │ 便宜模型  │
│  │ Fetch     │   │ SrcGraph │  │         │  │          │
│  │ AgentTool │   │          │  │         │  │          │
│  │ MCP Tools │   │          │  │         │  │          │
│  │ 主力模型  │   │ 便宜模型  │  │         │  │          │
│  └──────────┘   └──────────┘  └─────────┘  └──────────┘
└─────────────────────────────────────────────────┘
```

| Agent | 触发时机 | 工具 | 模型 |
|-------|---------|------|------|
| **Coder** | 用户发消息 | 全部 13 个 + MCP | 主力模型 |
| **Task** | Coder 调用 agentTool | 只读 5 个 | 便宜模型 |
| **Title** | 首次对话自动触发 | 0 个 | 最便宜模型 |
| **Summarizer** | 手动 / 自动触发 | 0 个 | 便宜模型 |

### 7.1 Agent 创建流程

```go
// agent.go:706 — Provider 创建
func createAgentProvider(agentName config.AgentName) (provider.Provider, error) {
    cfg := config.Get()
    agentConfig := cfg.Agents[agentName]          // 从配置取 Agent 配置
    model := models.SupportedModels[agentConfig.Model]  // 取模型元数据
    providerCfg := cfg.Providers[model.Provider]   // 取 API Key

    opts := []provider.ProviderClientOption{
        provider.WithAPIKey(providerCfg.APIKey),
        provider.WithModel(model),
        provider.WithSystemMessage(prompt.GetAgentPrompt(agentName, model.Provider)),
        provider.WithMaxTokens(agentConfig.MaxTokens),
    }

    // Per-model 推理配置
    if model.Provider == ProviderOpenAI {
        provider.WithReasoningEffort(agentConfig.ReasoningEffort)  // low/medium/high
    }
    if model.Provider == ProviderAnthropic {
        provider.WithAnthropicShouldThinkFn(DefaultShouldThinkFn)
    }

    return provider.NewProvider(model.Provider, opts...)
}
```

---

## 8. 子 Agent 委托

### 8.1 agentTool — 唯一的"嵌套"工具

```go
// agent-tool.go:43 — 工具执行
func (b *agentTool) Run(ctx context.Context, call tools.ToolCall) (tools.ToolResponse, error) {
    var params AgentParams
    json.Unmarshal([]byte(call.Input), &params)

    // 创建子 Agent（AgentTask 类型，只有只读工具）
    agent, _ := NewAgent(config.AgentTask, ...)

    // 创建独立的子 Session
    session, _ := b.sessions.CreateTaskSession(ctx, call.ID, parentSessionID, "New Agent Session")

    // 运行子 Agent，阻塞等待
    done, _ := agent.Run(ctx, session.ID, params.Prompt)
    result := <-done  // 阻塞直到子 Agent 完成

    // 子 Session 的费用合并到父 Session
    parentSession.Cost += updatedSession.Cost

    return tools.NewTextResponse(result.Message.Content().String()), nil
}
```

**子 Agent 特点：**
- AgentTask 只有 **5 个只读工具**（Glob/Grep/LS/View/Sourcegraph）
- 独立 Session，费用独立追踪
- **阻塞等待** —— 不支持并行多子 Agent
- 子 Agent 只能搜索查看，不能修改文件

---

## 9. 工具系统

### 9.1 BaseTool 接口

```go
// tools/tools.go:69 — 最简工具接口
type BaseTool interface {
    Info() ToolInfo           // 名称、描述、参数 Schema
    Run(ctx context.Context, params ToolCall) (ToolResponse, error)
}
```

只有 2 个方法。对比 Hermes 的注册表系统，这是 Go 式的极致简约。

### 9.2 工具注册

```go
// agent/tools.go — 手动组装
func CoderAgentTools(...) []tools.BaseTool {
    return []tools.BaseTool{
        tools.NewBashTool(permissions),
        tools.NewEditTool(lspClients, permissions, history),
        tools.NewFetchTool(permissions),
        tools.NewGlobTool(),
        tools.NewGrepTool(),
        tools.NewLsTool(),
        tools.NewSourcegraphTool(),
        tools.NewViewTool(lspClients),
        tools.NewPatchTool(lspClients, permissions, history),
        tools.NewWriteTool(lspClients, permissions, history),
        NewAgentTool(sessions, messages, lspClients),  // 子 Agent
        GetMcpTools(ctx, permissions)...,               // MCP 工具
    }
}
```

纯手工列表，没有反射、没有 AST、没有魔法。**修改工具列表 = 修改这个函数。**

### 9.3 MCP 工具集成

```go
// mcp-tools.go — MCP 工具包装器
type mcpTool struct {
    mcpName     string
    tool        mcp.Tool
    mcpConfig   config.MCPServer
    permissions permission.Service
}

func (b *mcpTool) Info() tools.ToolInfo {
    return tools.ToolInfo{
        Name:   fmt.Sprintf("%s_%s", b.mcpName, b.tool.Name),  // "mcpServerName_toolName"
        ...
    }
}

func (b *mcpTool) Run(ctx context.Context, call tools.ToolCall) (tools.ToolResponse, error) {
    // 标准 MCP 协议: Initialize → CallTool
    client := createMCPClient(b.mcpConfig)
    client.Initialize(ctx, ...)
    result := client.CallTool(ctx, ...)
    return result
}
```

**MCP Tool 命名策略：** `{服务器名}_{工具名}`，如 `filesystem_read_file`。这避免了命名冲突，但也导致工具名较长。

### 9.4 内置工具一览

| 工具 | 功能 | 权限控制 |
|------|------|---------|
| **Bash** | 执行 Shell 命令 | ✅ Permission |
| **Edit** | LSP 驱动的智能代码编辑 | ✅ Permission |
| **View** | 读取文件（带行号） | ❌ |
| **Write** | 写入文件 | ✅ Permission |
| **Patch** | 应用 diff patch | ✅ Permission |
| **Glob** | 文件名搜索 | ❌ |
| **Grep** | 内容搜索（ripgrep） | ❌ |
| **LS** | 列目录 | ❌ |
| **Fetch** | HTTP GET URL（支持 text/markdown/html 提取） | ✅ Permission |
| **Sourcegraph** | 搜索公开代码仓库 | ❌ |
| **Diagnostics** | LSP 诊断信息 | ❌ |
| **Agent** | 启动子 Agent | ❌ |

---

## 10. Provider 层

### 10.1 Provider 接口

```go
// provider/provider.go:53-59
type Provider interface {
    SendMessages(ctx, messages, tools) (*ProviderResponse, error)  // 非流式
    StreamResponse(ctx, messages, tools) <-chan ProviderEvent       // 流式 (Channel)
    Model() models.Model
}
```

没有 adapter 抽象层。每个 Provider 直接实现这两个方法，在内部处理消息格式转换。

### 10.2 支持的 Provider

| Provider | 文件 | 消息格式 |
|----------|------|---------|
| Anthropic | anthropic.go (472行) | Messages API |
| OpenAI | openai.go | Chat Completions |
| Gemini | gemini.go | Generative Language API |
| Copilot | copilot.go | GitHub Copilot API |
| Azure | azure.go | Azure OpenAI |
| Bedrock | bedrock实现 (在anthropic.go内) | AWS Bedrock |
| Groq | groq.go | Chat Completions |
| XAI | xai.go | Chat Completions |
| Vertex AI | vertexai.go | Google Vertex AI |
| Local | local.go | 本地模型 |

### 10.3 重试机制

```go
// provider/provider.go:15
const maxRetries = 8  // 最多重试 8 次

// 每个 Provider 的 stream() 内部实现重试
// 通过 <-chan ProviderEvent 通知上层
```

不同于 Hermes 的分类重试（瞬态/超限/过滤分别处理），OpenCode 的策略更简单：**统一重试，最多 8 次**。

### 10.4 Anthropic 前缀缓存

```go
// provider/anthropic.go:60-73
func (a *anthropicClient) convertMessages(messages []message.Message) ... {
    for i, msg := range messages {
        cache := false
        if i > len(messages)-3 {   // 最后3条消息标记缓存
            cache = true
        }
        // ...
        if cache && !a.options.disableCache {
            content.CacheControl = anthropic.CacheControlEphemeralParam{Type: "ephemeral"}
        }
    }
}
```

与 Hermes 的 Stable/Context/Volatile 三段式不同，OpenCode 的策略是**最后 3 条消息启用前缀缓存**——简单直接。

---

## 11. 消息数据模型

### 11.1 Message 结构体

```go
// message/content.go:111
type Message struct {
    ID        string           // UUID
    Role      MessageRole      // "assistant" / "user" / "system" / "tool"
    SessionID string
    Parts     []ContentPart    // 多态内容片段
    Model     models.ModelID
    CreatedAt int64
    UpdatedAt int64
}
```

### 11.2 ContentPart —— 多态内容接口

```go
type ContentPart interface { isPart() }

// 7 种内容类型:
type ReasoningContent struct { Thinking string }  // 模型思考
type TextContent struct { Text string }           // 文本
type ImageURLContent struct { URL, Detail string } // 图片 URL
type BinaryContent struct { Path, MIMEType, Data } // 二进制（base64）
type ToolCall struct { ID, Name, Input, Type, Finished } // 工具调用
type ToolResult struct { ToolCallID, Content, Metadata, IsError } // 工具结果
type Finish struct { Reason FinishReason; Time int64 } // 结束标记
```

**设计亮點：** 一条 Message 可以包含多种 Part 的有序列表。比如 Assistant 消息可以是：
```
[ReasoningContent, TextContent, ToolCall, ToolCall, Finish]
```

这与 OpenAI/Anthropic 的 content blocks 结构对应。

### 11.3 FinishReason

```go
const (
    FinishReasonEndTurn          = "end_turn"
    FinishReasonMaxTokens        = "max_tokens"
    FinishReasonToolUse          = "tool_use"
    FinishReasonCanceled         = "canceled"
    FinishReasonError            = "error"
    FinishReasonPermissionDenied = "permission_denied"
)
```

`FinishReasonToolUse` 是循环继续的信号；
其他所有原因都是循环结束的信号。

---

## 12. 会话管理

### 12.1 Session 结构体

```go
type Session struct {
    ID               string         // UUID
    ParentSessionID  string         // 子 Agent 的父 Session
    Title            string         // 会话标题
    MessageCount     int64
    PromptTokens     int64
    CompletionTokens int64
    SummaryMessageID string         // 摘要消息 ID (压缩点)
    Cost             float64        // 累计费用
    CreatedAt        int64
    UpdatedAt        int64
}
```

### 12.2 Session 层级

```
ParentSession (用户对话)
    │
    ├─ TitleSession (title-ParentSessionID)     ← 标题生成
    │
    ├─ TaskSession (toolCallID)                 ← 子Agent 1
    │
    └─ TaskSession (toolCallID)                 ← 子Agent 2
```

`ParentSessionID` 实现了简单的 Session 树。子 Session 的费用合并到父 Session。

### 12.3 存储

- **SQLite** 数据库
- 通过 [sqlc](https://sqlc.dev/) 生成类型安全的查询代码
- Session 和 Message 各有独立的 Service 层（Go interface 实现）

---

## 13. 权限安全模型

### 13.1 Permission Service

```go
type Service interface {
    pubsub.Subscriber[PermissionRequest]
    GrantPersistant(permission PermissionRequest)     // 持久授权（本 Session 记住）
    Grant(permission PermissionRequest)              // 单次授权
    Deny(permission PermissionRequest)               // 拒绝
    Request(opts CreatePermissionRequest) bool       // 请求权限（阻塞等待）
    AutoApproveSession(sessionID string)             // 自动授权整个 Session
}
```

### 13.2 权限检查流程

```
工具.Run()
    │
    ▼
permissions.Request(CreatePermissionRequest{
    ToolName: "bash",
    Action:   "execute",
    Path:     "/project",
    Params:   {command: "rm -rf ..."},
})
    │
    ├─ autoApproveSession?  → 直接通过
    ├─ 之前已 GrantPersistant? → 直接通过
    └─ 否则 → 发布到 pubsub → 阻塞等待 UI 层确认
```

**阻塞设计：** `Request()` 创建一个 Channel，阻塞等待 UI 层的 `Grant()`/`Deny()` 响应。这是一种**同步权限模型**，而不是 Hermes 的回调式。

---

## 14. LSP 集成

### 14.1 架构

```
App.initLSPClients()
    │
    ├─ lsp.NewClient(ctx, "gopls")     ← 启动 LSP 进程
    ├─ lspClient.InitializeLSPClient()  ← 握手
    ├─ lspClient.WaitForServerReady()   ← 等待就绪
    └─ go watcher.WatchWorkspace()      ← 后台监听文件变化
```

### 14.2 LSP 功能

- **DiagnosticsTool** — 获取当前文件的诊断信息（错误/警告）
- **EditTool** — 使用 LSP 进行智能编辑（格式化、重构）
- **ViewTool** — 利用 LSP 符号信息增强代码浏览

### 14.3 并发安全

```go
// 共享的 LSP 客户端 map
app.LSPClients map[string]*lsp.Client
app.clientsMutex sync.RWMutex       // 读写锁保护

// LSP 崩溃自动重启
defer logging.RecoverPanic("LSP-"+name, func() {
    app.restartLSPClient(ctx, name)
})
```

---

## 15. Pub/Sub 事件总线

### 15.1 Broker

```go
// 类型参数化的泛型 Broker
type Broker[T any] struct { ... }

func NewBroker[T any]() *Broker[T] { ... }
func (b *Broker[T]) Subscribe() <-chan T { ... }
func (b *Broker[T]) Publish(eventType EventType, payload T) { ... }
```

### 15.2 使用方

```go
// Agent 发布事件
agent.Publish(pubsub.CreatedEvent, AgentEvent{...})

// UI 订阅事件
events := agent.Subscribe()
for event := range events {
    // 更新 UI
}
```

**Go 泛型 (1.18+) 的典型应用：** `Broker[AgentEvent]`、`Broker[Session]`、`Broker[Message]` 复用同一份代码，类型安全。

---

## 16. 上下文管理

### 16.1 摘要式压缩

```go
// Summarize() — agent.go:535
func (a *agent) Summarize(ctx, sessionID) error {
    // 1. 加载全部消息
    msgs := a.messages.List(ctx, sessionID)

    // 2. 追加摘要指令
    promptMsg := Message{
        Role:  User,
        Parts: []ContentPart{TextContent{"Provide a detailed but concise summary..."}},
    }
    msgsWithPrompt := append(msgs, promptMsg)

    // 3. 用 SummarizeProvider 生成摘要（便宜模型，无工具）
    response := a.summarizeProvider.SendMessages(ctx, msgsWithPrompt, []tools.BaseTool{})

    // 4. 创建摘要消息（标注为 Assistant 角色）
    msg, _ := a.messages.Create(ctx, sessionID, CreateMessageParams{
        Role:  message.Assistant,
        Parts: []ContentPart{TextContent{summary}, Finish{...}},
        Model: summarizeProvider.Model().ID,
    })

    // 5. 记录摘要位置
    session.SummaryMessageID = msg.ID
    sessions.Save(ctx, session)
}
```

**摘要后效果：** 下次 `processGeneration()` 会检测 `SummaryMessageID`，丢弃摘要消息之前的所有消息，以此实现上下文压缩。

### 16.2 与 Hermes 的区别

| | OpenCode | Hermes |
|------|----------|--------|
| 压缩方式 | 独立 Agent 生成摘要 → 截断 | ContextCompressor（辅助 LLM + 结构化模板） |
| 摘要后 | 丢弃旧消息 | 保护头尾 + 摘要中间 |
| 触发 | 手动/自动 | 自动（75% 阈值） |
| 迭代压缩 | 否 | 是 |

---

## 17. 设计模式与亮点

| # | 模式 | 代码位置 | 说明 |
|---|------|---------|------|
| 1 | **接口隔离** | `agent.Service` | 8 个方法，不臃肿 |
| 2 | **泛型 Broker** | `pubsub.Broker[T]` | Go 1.18+ 类型安全的 Pub/Sub |
| 3 | **多 Agent 分离** | 4 种 Agent 类型 | 标题/摘要用便宜模型，省 90% 费用 |
| 4 | **阻塞权限模型** | `Permission.Request()` | Channel 阻塞等待 UI 确认 |
| 5 | **流式实时持久化** | `processEvent()` | 每个 delta 写入 SQLite |
| 6 | **Context 取消** | `ctx.Done()` | 标准 Go 模式 |
| 7 | **Panic 恢复** | `logging.RecoverPanic` | Goroutine 边界防护 |
| 8 | **Session 树** | `ParentSessionID` | 子 Agent 费用合并 |
| 9 | **手动工具注册** | `CoderAgentTools()` | 无反射、无魔法 |
| 10 | **Message Parts 多态** | `ContentPart` 接口 | 可扩展的内容类型系统 |

---

## 18. 局限与边界

| 局限 | 说明 |
|------|------|
| **无记忆系统** | 不记住用户偏好或历史事实 |
| **无技能积累** | 学不会"怎么做某件事" |
| **无迭代预算** | `for {}` 死循环，只靠 LLM 自己停 |
| **无多平台** | 只有 TUI，不支持微信/Slack/Telegram |
| **无定时任务** | 没有 Cron |
| **无图像生成** | 只能处理，不能生成 |
| **单子 Agent** | agentTool 阻塞等待，不支持并行 |
| **无离线回退** | 不工作 |
| **手动摘要** | 上下文压缩需要手动触发（或配置 `autoCompact`） |
| **工具列表固定** | 无 toolset 概念，全有或全无 |

---

**一句话总结：** OpenCode 的 Agent 核心层是 **Go 语言极简主义的典范** —— 758 行实现了一个完整的多 Agent 协作系统，接口干净、事件驱动、实时持久化，但功能边界明确限定在编码场景，不做记忆/技能/多平台等"非编码"需求。
