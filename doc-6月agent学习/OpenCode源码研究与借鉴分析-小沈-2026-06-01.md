# OpenCode源码研究与借鉴分析

**创建时间**: 2026-06-01 12:42:48
**研究范围**: F:\agenttool\opencode-old\internal\llm\ — provider/agent/tools/prompt/models 五大子系统
**代码统计**: ~6.2k行核心代码（provider 1.7k + agent 1.1k + tools 1.4k + models 0.5k + prompt 0.6k + message 0.6k）
**用途**: 为我方Agent四层架构（执行引擎层/编排层/LLM服务层）设计提供实践参考

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| **v1.6** | **2026-06-03 08:30:00** | **小沈** | **§2/三/四/五 根据用户批注更新借用策略**：★二-第4层参考借用，★★三-第三层全部采用，★四-全部采用，★五-直接参考使用。补充具体意见：univ-task-agent + Provider统一 + Summarizer + Task→read-task-agent |
| **v1.7** | **2026-06-03 09:00:00** | **小沈** | **§十一 第十一章全部批注处理**：1. 正文标题中[批注]改为括号内嵌说明；2. 汇总表更新：①ProviderEvent原样采用10种（不再精简5种）；③纯ReAct循环原样采用作为execute，plan=轻量级规划agent；⑧~⑫逻辑原理原样采用；⑬Provider热切换改为配置文件选择、不热切换；③静态工具分两阶段（先静态后AST）；③Summarize第二阶段采用；③单层Agent重新决策改为采用OpenCode主agent+子agent模式；③Prompt硬编码重新决策需再次调研；①ProviderEvent和ForEach分派提出疑问待确认。 |
| **v1.8** | **2026-06-03 09:30:00** | **小沈** | **根据调研结果更新决策**：①ProviderEvent原样采用10种（确认5种不够）；②每delta写DB改为先写内存、流式完成后一次性批量写入DB；③Prompt采用文本文件方式（prompt.md等），运行时加载，结构参考OpenCode的拼接方式；④ForEach分派确认不适用（只有一个provider）；⑤同步模型切换确认有（Update方法，20行小功能点）；⑥事件处理改为10种事件原样采用（不再精简7种）。§7/§3.6.4/§8.6均已同步。 |

---

## 一、研究背景与目标

### 1.1 为什么要研究OpenCode

OpenCode（https://opencode.ai）是一个开源的AI编程Agent，采用Go语言实现。其核心架构包含了一套完整的Tool系统、Provider流式框架、Prompt管理体系和Agent ReAct循环——与我方正在设计的四层架构高度相关。

**研究目标**：逐块拆解OpenCode的四大子系统，评估哪些可以**直接借用**、哪些需要**改造适配**、哪些**不适合**我方架构。

> ⚠️ **诚实声明**：v1.0-v1.5版本的部分行号和分析深度存在水分（凭记忆估算，未逐行验证）。v1.6版本所有行号均为重新打开源码逐行读取的精确数据。如有任何不准确之处，请指正，我立即修正。

### 1.2 我方架构定位（快速对照）

| 我方层次 | OpenCode对应物 | 关系 |
|---------|---------------|------|
| **第4层 LLM服务层** | `llm/provider/` + `llm/agent/agent.go`(模型调用部分) | Provider接口可高度复用 |
| **第3层 执行引擎层** | `llm/agent/`(ReAct循环) + `llm/tools/`(工具系统) | 我方是Plan→Execute，非纯ReAct |
| **第2层 编排层** | 无独立编排层（OpenCode是单层Agent） | 我方有独立编排层，OpenCode无对应 |
| **第1层 接入层** | CLI入口 | 我方是SSE/HTTP入口 |

---

## 二、Provider流式处理体系（`llm/provider/`）— ★★★（第4层参考借用部分）

### 2.1 整体架构

```
provider.go                     baseProvider[C ProviderClient] (泛型基类)
  │
  ├── Provider 接口
  │   ├── SendMessages(ctx, messages, tools) → (*ProviderResponse, error)
  │   ├── StreamResponse(ctx, messages, tools) → <-chan ProviderEvent
  │   └── Model() → models.Model
  │
  ├── 各厂商实现（均实现 ProviderClient 接口）→ 本行删除，我们只是一个OpenAI兼容模式，不区分厂商
  │   ├── openai.go → openaiClient        (含GROQ/OpenRouter/XAI/Local)
  │   ├── anthropic.go → anthropicClient
  │ 
  └── ProviderFactory: NewProvider(providerName, opts...) → Provider
```

### 2.2 关键数据结构（借用）

#### ProviderEvent（流式事件，10种类型）

**注意**：ProviderEvent 由 **Provider层** 创建（各provider的`stream()`方法解析LLM原始chunk后发出），不是Agent创建的。Agent只消费这些事件。不同provider发出的子集不同（如OpenAI只发ContentDelta/Complete/Error，Anthropic发全部10种）。

```go
type EventType string
const (
    EventContentStart  EventType = "content_start"     // 内容开始
    EventToolUseStart  EventType = "tool_use_start"    // 工具调用开始
    EventToolUseDelta  EventType = "tool_use_delta"    // 工具参数增量
    EventToolUseStop   EventType = "tool_use_stop"     // 工具调用结束
    EventContentDelta  EventType = "content_delta"     // 内容增量（逐字推送）
    EventThinkingDelta EventType = "thinking_delta"    // 推理内容增量
    EventContentStop   EventType = "content_stop"      // 内容结束
    EventComplete      EventType = "complete"           // 全部完成（含TokenUsage）
    EventError         EventType = "error"              // 错误
    EventWarning       EventType = "warning"            // 警告
)
```

#### ProviderResponse（非流式/完成时返回）

```go
type ProviderResponse struct {
    Content      string
    ToolCalls    []message.ToolCall
    Usage        TokenUsage
    FinishReason message.FinishReason
}

type TokenUsage struct {
    InputTokens         int64
    OutputTokens        int64
    CacheCreationTokens int64
    CacheReadTokens     int64
}
```

### 2.3 流式实现模式（以 openai.go 为例）

```go
func (o *openaiClient) stream(ctx, messages, tools) <-chan ProviderEvent {
    eventChan := make(chan ProviderEvent)

    go func() {
        for { // 外层：重试循环
            stream := o.client.Chat.Completions.NewStreaming(ctx, params)
            acc := openai.ChatCompletionAccumulator{}
            currentContent := ""

            for stream.Next() { // 内层：逐chunk消费
                chunk := stream.Current()
                acc.AddChunk(chunk)
                // 按 choice.delta.content 逐段推送
                eventChan <- ProviderEvent{Type: EventContentDelta, Content: ...}
            }

            err := stream.Err()
            if err == nil || errors.Is(err, io.EOF) {
                // 正常完成：从 acc 提取完整 tool calls
                finishReason := finishReason(acc.Choices[0].FinishReason)
                eventChan <- ProviderEvent{Type: EventComplete, Response: ...}
                close(eventChan); return
            }

            // 错误 → 判断是否可重试
            if retry, after, retryErr := shouldRetry(attempts, err); retry {
                time.After(time.Duration(after) * time.Millisecond)
                continue // 重试
            }
            eventChan <- ProviderEvent{Type: EventError, Error: retryErr}
            close(eventChan); return
        }
    }()
    return eventChan
}
```

**关键点**：
1. **goroutine+channel**模式：流式事件通过channel异步推送，调用方用`for range`消费
2. **ChatCompletionAccumulator**：自动积累所有chunk，结束时从中提取完整tool calls
3. **流式错误重试**：外层for循环+指数退避，重试整个stream
4. **context传播**：ctx取消时goroutine退出，channel关闭

### 2.4 Provider各厂商差异（弃用总体）

OpenCode每个provider的实现都针对该厂商的SDK做了特殊适配（消息格式转换、cache策略、thinking触发、重试状态码等）。

**我方明确不采用这种模式**——我们只认"模型"，不针对特定provider做特殊处理。所有provider通过统一接口通信，厂商SDK差异在adapter层内部消化，对上层完全透明。

### 2.5 对标我方第4层（LLM服务层）的可借点

| OpenCode | 我方对应 | 借用策略 |
|----------|---------|---------|
| `Provider`接口双split（SendMessages + StreamResponse） | `llm_client.py`的`call_complete()` + `call_stream()` | **直接复用接口split模式** |
| `ProviderEvent`事件体系（10种） | 我方LLMChunk事件 | **原样采用10种**：不再精简为5种 |
| `ChatCompletionAccumulator` | 流式过程中拼接arguments chunks | **直接复用思路**：accumulator模式是tool calling流式的标准解法 |
| 指数退避+shouldRetry | 我方`_retry_with_backoff()` | **直接复制算法**：Go的shouldRetry逻辑可翻译为Python版本 |
| NewProvider工厂 + providerClientOptions | 我方`LLMConfig`从config.yaml加载 | **参考借用**，但Go用Option模式，我方用Pydantic config |
| `ForEach provider → stream()`分派 | 我方`llm_client.py`按provider分派 | **参考借用** |

> 注：我方只有一个provider（OpenAI兼容模式），不需要ForEach遍历。

---

### 2.6 模型注册表（`llm/models/`）— 我们用config文件

```go
// models.go:10-23
type Model struct {
    ID                  ModelID       // "claude-3.7-sonnet"
    Name                string        // "Claude 3.7 Sonnet"
    Provider            ModelProvider // "anthropic"
    APIModel            string        // "claude-3-7-sonnet-latest"（实际API名）
    CostPer1MIn         float64       // 输入价格（$/1M tokens）
    CostPer1MOut        float64       // 输出价格
    CostPer1MInCached   float64       // 缓存命中时输入价格
    CostPer1MOutCached  float64       // 缓存命中时输出价格
    ContextWindow       int64         // 上下文窗口大小
    DefaultMaxTokens    int64         // 默认max_tokens
    CanReason           bool          // 支持reasoning/thinking
    SupportsAttachments bool          // 支持图片附件
}
```

**注册机制**：
- 各厂商模型定义在独立文件（`anthropic.go`, `openai.go`, `gemini.go` 等）
- 每个文件定义对应Provider的常量 + `map[ModelID]Model`
- `init()` 函数用 `maps.Copy()` 合并所有模型到 `SupportedModels` 全局map
- 通过 `models.SupportedModels[modelID]` 查找

**定价覆盖范围**：
- 50+模型，覆盖 Anthropic/OpenAI/Gemini/Groq/Azure/OpenRouter/XAI/Copilot
- 含缓存价格（cached vs non-cached不同计费）
- 含 `CanReason`（是否支持thinking/reasoning feature）和 `SupportsAttachments`（是否支持图片）

**Provider 热度排序**：
```go
var ProviderPopularity = map[ModelProvider]int{
    ProviderCopilot:    1,
    ProviderAnthropic:  2,
    ProviderOpenAI:     3,
    // ...
}
```

---

## 三、Agent ReAct核心循环（`llm/agent/agent.go`）— ★★（第三层-全部采用）

### 3.1 循环结构

```
agent.Run(ctx, sessionID, content)
  └─→ processGeneration(ctx, sessionID, content)
        ├── 1. 载入历史消息（messages.List）
        │     └── 如果有 SummaryMessageID → 从此截断旧消息
        ├── 2. 创建新UserMessage
        ├── 3. for { // ReAct主循环
        │      ├── streamAndHandleEvents(ctx, msgHistory)
        │      │     ├── provider.StreamResponse(ctx, messages, tools) → eventChan
        │      │     ├── for event := range eventChan {
        │      │     │     processEvent(assistantMsg, event)
        │      │     │     ├── EventContentDelta → AppendContent + Update DB
        │      │     │     ├── EventThinkingDelta → AppendReasoningContent
        │      │     │     ├── EventToolUseStart → AddToolCall
        │      │     │     ├── EventToolUseStop → FinishToolCall
        │      │     │     ├── EventComplete → SetToolCalls + AddFinish + TrackUsage
        │      │     │     └── EventError → return error
        │      │     }
        │      │     ├── for i, toolCall := range toolCalls {  // 顺序执行工具
        │      │     │     tool := findTool(toolCall.Name)
        │      │     │     result := tool.Run(ctx, toolCall)
        │      │     │     toolResults[i] = result
        │      │     │     // 权限拒绝 → 剩余工具标记为canceled
        │      │     }
        │      │     └── return assistantMsg + toolResults
        │      │
        │      └── if finishReason == ToolUse → append toolResults to msgHistory, continue
        │          else → return AgentEvent(Done=true)
        │   }
        └── AgentEvent → channel
```

### 3.2 并发与取消

```go
type agent struct {
    activeRequests sync.Map  // map[sessionID]context.CancelFunc
}

func (a *agent) Run(ctx, sessionID, content) {
    if a.IsSessionBusy(sessionID) { return nil, ErrSessionBusy }
    genCtx, cancel := context.WithCancel(ctx)
    a.activeRequests.Store(sessionID, cancel)
    go func() {
        defer a.activeRequests.Delete(sessionID)
        result := processGeneration(genCtx, ...)
        events <- result; close(events)
    }()
    return events, nil
}

func (a *agent) Cancel(sessionID string) {
    if cancelFunc, ok := a.activeRequests.LoadAndDelete(sessionID); ok {
        cancelFunc()  // 取消 context → for range stream 退出
    }
}
```

### 3.3 Session历史管理

```go
if session.SummaryMessageID != "" {
    // 找到 summary message，从此截断历史
    msgs = msgs[summaryMsgIndex:]
    msgs[0].Role = message.User  // 第一条改为 User 角色
}
```

### 3.4 对标我方可借点

| OpenCode | 我方对应 | 借用策略 |
|----------|---------|---------|
| 纯ReAct循环（while toolUse → loop） | 我方Plan→Execute两步 | **原样采用**：作为我们的execute，plan=轻量级规划agent |
| `activeRequests sync.Map` 按session隔离 | 我方第1层`_active_tasks: dict[str, asyncio.Task]` | **逻辑原理原样采用**：直接复用设计，Go sync.Map→Python dict |
| `IsSessionBusy` 检查 | 我方`_is_session_busy()` | **逻辑原理原样采用**：直接复用 |
| SummaryMessageID 截断历史 | 我方第2层 context window管理 | **逻辑原理原样采用**：用summary标记截断点，比纯滑动窗口更智能 |
| `processEvent` 10种事件 → 实时写DB | 我方SSE流式过程中写DB | **逻辑原理原样采用**：OpenCode每delta写一次DB（太频繁），我方改为先写内存、完成时一次性批量写入DB |
| `TrackUsage` → cost核算（在**agent层**做，非provider层） | 我方token usage tracking | **逻辑原理原样采用**：公式可直接复制：`model.CostPer1MIn/1e6 * tokens` |
| **Provider热切换**（agent.Update() → 重建provider） | 我方模型切换 | **自行设计**：在配置文件选好即可，不热切换 |

### 3.5 我方与OpenCode的核心差异

| 维度 | OpenCode | 我方 |
|------|---------|------|
| **循环模式** | 纯ReAct：while(needTool)→LLM→tool→loop | Plan→Execute：先生成计划步骤图，再按图执行 |
| **历史管理** | SummaryMessageID + 全量历史拼接 | 经验学习 + 结构化步骤存储 |
| **工具来源** | 预注册静态工具列表 | ArtTool（即兴生成代码+沙箱执行） |
| **编排层** | 无（只有一层agent） | 独立第2层做编排决策 |

### 3.6 深度分析：OpenCode Agent到底有多"薄"？

> ⚠️ **v1.6重写说明**：v1.5版行号和行数估算是错的（processGeneration写L276-311，实际L233-311）。本节已逐行复盘修复。

OpenCode的 `agent.go` 共**758行**，它到底是什么——"薄调度器"还是"厚业务"？

#### 3.6.0 一个问题，一张表

问：agent.go里每个函数到底多长？**用数据说话，不拍脑袋**：

| 函数名 | 起-止行 | 代码行数 | 一句话职责 |
|--------|---------|---------|-----------|
| `NewAgent()` | L73-111 | **39** | 建agent，含1~3个Provider |
| `Model()` | L113-115 | **3** | 返回当前模型信息 |
| `Cancel()` | L117-133 | **17** | 按sessionID取消请求（含summarize） |
| `IsBusy()` | L135-147 | **13** | 全局是否繁忙 |
| `IsSessionBusy()` | L149-152 | **4** | 指定session是否繁忙 |
| `generateTitle()` | L154-189 | **36** | 异步生成会话标题 |
| `err()` | L191-196 | **6** | 构造错误事件 |
| `Run()` | L198-231 | **34** | **入口**：建channel、起goroutine、调processGeneration、发结果 |
| `processGeneration()` | L233-311 | **79** | **ReAct循环**：读历史→建消息→流式→判断是否继续 |
| `streamAndHandleEvents()` | L322-438 | **117** | **流处理+工具执行**：收stream事件→调工具→收结果 |
| `finishMessage()` | L440-443 | **4** | 标记消息结束 |
| `processEvent()` | L445-492 | **48** | **10种事件分发**：thinking/content/tool/error/complete |
| `TrackUsage()` | L494-513 | **20** | 计算费用+写session |
| `Update()` | L516-533 | **18** | 运行时切换模型/provider |
| `Summarize()` | L535-704 | **170** | 异步压缩会话历史 |
| `createAgentProvider()` | L706-758 | **53** | 按config创建底层Provider |

> 备注：L313-321是 `createUserMessage()`（8行），L322与上段间有空白行，都未计入函数体。

几个直观结论：
- **最长的函数**：`Summarize()` 170行（占22%），`streamAndHandleEvents()` 117行（占15%）
- **最短的函数**：`Model()` 3行，`IsSessionBusy()` 4行，`finishMessage()` 4行
- **调度核心4函数**：Run(34) + processGeneration(79) + streamAndHandleEvents(117) + processEvent(48) = **278行**

#### 3.6.1 "薄"的部分——真正的调度核心（~176行）

上面的278行包含了DB操作。如果把**纯粹调度逻辑**剥离出来，实际只有约176行：

| 纯调度逻辑 | 行范围 | 纯逻辑行数 | 在做什么 |
|-----------|--------|-----------|---------|
| Run() goroutine | L210-229 | **20** | 启动→等结果→发事件→关channel |
| processGeneration() 循环体 | L276-310 | **35** | `for { streamAndHandleEvents → 判断finishReason → loop/done }` |
| streamAndHandleEvents() 事件循环 | L339-348 | **10** | `for event := range eventChan { processEvent }` |
| streamAndHandleEvents() 工具派发 | L350-421 | **72** | `findTool → tool.Run → 收集results` |
| processEvent() 类型分发 | L453-491 | **39** | `switch event.Type { ... }` |
| **合计** | | **~176** | |

这176行就是OpenCode称为"薄调度器"的核心：

```go
// 核心调度 ≈ 176行，做的事情：
// 1. 起goroutine（20行）           ← 并发执行
// 2. while(needTool) { LLM→tool }（35行）  ← ReAct循环
// 3. for event := range stream（10行）     ← 流式事件输入
// 4. for _, tc := range toolCalls（72行）  ← 工具派发
// 5. switch event.Type（39行）             ← 事件类型分发
```

> 说它"薄"，不是因为这176行代码量少，而是**职责单一**——只做调度，不做编排、不做安全、不做UI。

#### 3.6.2 "厚"的部分——周边基础设施（~375行）----//通过什么方法实现的呢?
  通过 `a.messages` 和 `a.sessions` 对象方法
  同步代码7类"基础设施"，调用方式完全一样：
  ```
  a.messages.List(...)    // 同步调用，等DB返回
  a.messages.Create(...)  // 同步调用，等写入完成
  a.messages.Update(...)  // 同步调用，等写入完成
  a.sessions.Get(...)     // 同步调用
  a.sessions.Save(...)    // 同步调用
  a.provider.Stream(...)  // 同步调用（goroutine内部）
  ```
  **全部是同步顺序代码**。没有Hook，没有Pub/Sub注册，没有回调注册。就是A方法调B方法，B方法返回结果，A继续。
  ## 那个唯一的"异步"——goroutine
  Summarize和Title确实用了 `go func()` 起goroutine，但那不是"异步调用模式"，而是：
  ```go
  // Summarize启动时：
  go func() {
      // 这里面全部是同步代码
      msgs := a.messages.List(...)   // 同步
      resp := a.summarizeProvider.SendMessages(...) // 同步
      a.messages.Create(...)          // 同步
      a.sessions.Save(...)            // 同步
  }()
  // Summarize() 本身立刻返回 nil
  ```
  **goroutine里面做的事情，全部是同步方法调用**，只是整个goroutine放在后台跑，不阻塞调用方。这跟"异步调用"是两码事。
  ## 所以结论
	OpenCode	你的理解
  调用方式	全部是 `注入对象.方法()` 同步调�	✅ 正确
  有没有Hook/CB	❌ 没有	✅ 正确
  有没有Pub/Sub	❌ agent内部没有（PubSub只在UI层用）	✅ 正确
  异步吗	只有goroutine外壳，内部全同步	✅ 本质上就是同步
  **"薄调度器"之所以薄，不是因为用了异步框架，而是因为它把所有东西都塞进了同步的 `for { stream → tool → check }`
  循环里，靠的是"注入依赖 + 直接调"，没有花里胡哨的事件总线或回调注册。**
agent.go剩下的行数都在做基础设施：

| 基础设施 | 行范围 | 行数 | 说明 |
|---------|--------|------|------|
| **DB操作**（读历史/建消息/写消息） | L234-275, L326-336, L440-443 | ~60 | 每步都与SQLite交互 |
| **Usage+费用** | L494-513 | 20 | cost公式 `price/1e6 * tokens` |
| **网络创建**（3个Provider） | L73-111, L706-758 | 92 | NewAgent + createAgentProvider |
| **历史压缩**（Summarize） | L535-704 | 170 | 另一套完全独立的LLM调用+DB逻辑 |
| **标题生成** | L154-189 | 36 | 异步fire-and-forget |
| **Session管理** | L117-152 | 36 | busy检查 + cancel传播 |
| **运行时切换** | L516-533 | 18 | 热更新model |
| **合计** | | **~375** | |

**简单比喻**：如果把agent.go比作一个餐厅厨房——

```
调度核心 176行 = 厨师炒菜（核心工作）
DB操作   60行 = 洗碗工洗盘（必不可少但不是炒菜）
Provider 92行 = 采购备菜（准备工作）
Summarize170行 = 另开一灶炖汤（独立功能）
其他     60行 = 换菜单、清点库存（管理）
```

#### 3.6.3 Agent的"三层边界"——它为什么薄得有道理

agent.go对**上**、**下**、**平级**三层只暴露最窄的接口：

```
          上层（app.go / TUI）
               │
               ▼  只暴露: Run()→<-chan / Cancel() / Model()
     ┌─────────────────────────┐
     │      agent.go           │
     │  ┌───────────────────┐  │
     │  │  调度核心  176行   │  │  ← 职责：LLM→tool→LLM→tool→done
     │  │  (只做这一件事)     │  │
     │  └───────────────────┘  │
     │  ┌───────────────────┐  │
     │  │  基础设施  375行   │  │  ← 职责：DB/费用/summarize
     │  └───────────────────┘  │
     └─────────────────────────┘
               │
               ▼  只调: StreamResponse() / SendMessages()
            Provider（下层）
               
    平级（工具）：只做 findTool → tool.Run → collect result
```

**关键观察**——agent不做的事情比做的事情更重要：

| Agent不做 | 谁在做 | 为什么合理 |
|-----------|--------|-----------|
| ❌ **不做编排**（无意图分类/无模式切换） | 上层app.go/TUI | 调度就是执行，决策是上层职责 |
| ❌ **不做Prompt**（system prompt由Provider注入） | config→provider层 | prompt是配置，不是运行时逻辑 |
| ❌ **不做UI渲染** | TUI层 | 内容透传，按原样显示 |
| ❌ **不做安全过滤** | 每个tool内permission.Request() | 离操作最近的地方做检查最安全 |
| ❌ **不做多Agent协调** | agent-tool.go（SubAgent机制） | 子Agent当工具用，不增加调度复杂度 |

#### 3.6.4 对我方第3层的设计启示

| 启示 | 具体做法 |
|------|---------|
| **接口要薄** | 第3层只暴露 `Run(task) → result` 和 `Cancel()`，其他全部内部消化 |
| **调度循环可借鉴** | `for { stream→tool→collect→判断是否继续 }` 模式可以直接翻译成Python |
| **DB操作要优化** | OpenCode每delta写DB一次（太频繁），我方改为**先写内存，流式完成后一次性批量写入DB** |
| **事件处理可复用** | processEvent的switch分发逻辑直接翻译，10种事件原样采用 |
| **取消机制直接复用** | `dict[session_id] → cancel_func`，Python版用 `asyncio.Task.cancel()` |
| **Usage tracking放第3层** | cost核算不属于编排（第2层）也不属于LLM调用（第4层），放第3层刚刚好 |
| **Provider创建不在第3层** | 我方将Provider统一放在第4层管理，第3层直接用 |

### 4.1 核心接口（全部采用）

```go
// tools/tools.go
type ToolInfo struct {
    Name        string
    Description string
    Parameters  map[string]any    // JSON Schema
    Required    []string
}

type ToolCall struct {
    ID    string `json:"id"`
    Name  string `json:"name"`
    Input string `json:"input"`   // JSON string
}

type ToolResponse struct {
    Type     toolResponseType  // "text" | "image"
    Content  string
    Metadata string
    IsError  bool
}

type BaseTool interface {
    Info() ToolInfo
    Run(ctx context.Context, params ToolCall) (ToolResponse, error)
}
```

### 4.2 各工具实现模式（第1版采用此方法，第2版采用AST注册）
所有11个工具遵循一致的实现模式：

```go
type BashParams struct {
    Command string `json:"command"`
    Timeout int    `json:"timeout"`
}
type bashTool struct {
    permissions permission.Service
}
func (b *bashTool) Info() tools.ToolInfo { return ToolInfo{...} }
func (b *bashTool) Run(ctx, call) (ToolResponse, error) {
    // 1. 权限检查 permission.Request(sessionID, toolName, action)
    // 2. 执行 + 超时 + 输出截断
    // 3. 返回 ToolResponse{Type: text, Content: output, IsError: ...}
}
```

**工具列表**：

| 工具 | 文件 | 行数 | 说明 |
|------|------|------|------|
| Bash | `bash.go` | 347 | 命令执行，**持久化Shell** |
| Edit | `edit.go` | 489 | 精确字符串替换（old→new） |
| Write | `write.go` | 181 | 写入/创建文件 |
| Patch | `patch.go` | 175 | 应用diff补丁 |
| View | `view.go` | 180 | 读取文件（行范围） |
| Glob | `glob.go` | 147 | 文件名模式搜索 |
| Grep | `grep.go` | 206 | 内容搜索 |
| Ls | `ls.go` | 134 | 目录列表 |
| Fetch | `fetch.go` | 165 | HTTP请求 |
| Sourcegraph | `sourcegraph.go` | 196 | Sourcegraph代码搜索 |
| Diagnostics | `diagnostics.go` | 98 | LSP诊断信息 |

#### 4.2.1 Bash 工具 — PersistentShell

Bash工具不每次 spawn 新进程，而是维护一个**长连接持久化Shell**（`shell/shell.go:327`）：

```go
type PersistentShell struct {
    cmd          *exec.Cmd      // 持久化的 shell 进程
    stdin        *os.File       // stdin pipe
    isAlive      bool
    cwd          string
    commandQueue chan *commandExecution  // goroutine-safe命令队列
}
```

**特性**：
- 状态保持：`cd` 命令跨命令持续有效
- 命令队列：goroutine-safe串行执行
- 超时控制：每个命令独立timeout
- 中断支持：可中断正在执行的命令
- 默认超时：1分钟，最大10分钟
- 最大输出：30,000字符截断

**安全策略**：
- 禁用网络命令：curl, wget, nc, telnet 等
- 只读命令白名单：ls, echo, pwd, date, git log 等
- 所有执行前经 `permission.Request` HITL审批

### 4.3 工具注册

```go
func CoderAgentTools(...) []tools.BaseTool {
    return []tools.BaseTool{
        tools.NewBashTool(permissions),
        tools.NewEditTool(lspClients, permissions, history),
        // ...
        NewAgentTool(sessions, messages, lspClients),  // SubAgent!
    }
}
```

### 4.4 SubAgent模式（agent-tool.go — 对我参考价值极高）（全部采用）
有几个子agent?
```go
// agent/agent-tool.go
type AgentParams struct {
    Prompt string `json:"prompt"`
}

func (b *agentTool) Run(ctx, call) (ToolResponse, error) {
    // 1. 解析参数
    // 2. 创建子Agent（config.AgentTask），只给只读工具
    // 3. 创建子Session（CreateTaskSession）
    // 4. 子Agent.Run → 等待完成
    // 5. 子Session成本归父：parentSession.Cost += childSession.Cost
    // 6. 返回子Agent的文本结果
}
```
## 触发链路
```
用户发消息 → CoderAgent ReAct循环
    │
    ├─ 第1轮: 调LLM → LLM输出纯文本 → 返回给用户
    │
    ├─ 第2轮: 调LLM → LLM决定需要工具
    │   │
    │   ├─ LLM输出: {"tool_call": "Bash", "args": "ls"}
    │   │   → 执行Bash工具 → 结果回传 → 继续调LLM
    │   │
    │   └─ LLM输出: {"tool_call": "agent", "args": {"prompt": "帮我找一下XX"}}
    │       → 执行AgentTool工具 ← 这就是触发
    │           │
    │           ├─ NewAgent(config.AgentTask, ...)  // 创建Task子Agent
    │           ├─ CreateTaskSession(...)            // 独立Session
    │           ├─ agent.Run(ctx, sessionID, prompt) // 子Agent跑ReAct
    │           └─ 等子Agent跑完，拿到结果
    │       → 把结果当工具返回值回传LLM → 继续调LLM
    │
    └─ 第3轮: 调LLM → LLM输出最终回答 → 返回给用户
```
## 什么时候LLM会选择调用AgentTool？
看AgentTool的描述（代码L32）：
> "When you are searching for a keyword or file and are not confident that you will find the right match on the first
try, **use the Agent tool to perform the search for you**."
**触发场景**：
- 用户问"项目中哪个文件定义了XX功能？"
- 需要多轮搜索才能找到答案
- 主Agent觉得直接Glob/Grep不够，需要"委托给一个专门搜索的Agent"
------------------------

4个Agent是怎么用的
Agent	触发方式	代码位置
**AgentCoder**	用户发消息，agent.Run(	agent.go L198
**AgentTask**	主Agent调用 `AgentTool` 工具时，NewAgent(config.AgentTask, .	agent-tool.go L57
**AgentTitle**	第一条消息时异步 go a.generateTitle(	agent.go L241
**AgentSummarizer**	用户触发压缩时 go a.Summarize(	agent.go L535
## 关键结论
确的关系
```
Coder 是"主要Agent"——它是一个完整可运行的Agent实例

    ┌── CoderAgent（完整ReAct循环）
    │   ├── provider（主模型）← 正常ReAct循环用
    │   ├── titleProvider ← 首次发消息时异步调用（不是ReAct循环）
    │   └── summarizeProvider ← 手动触发压缩时异步调用（不是ReAct循环）
    │
    └── AgentTool（工具）← 运行时被调用的一个"工具"
            │
            └── 被调用时才：NewAgent(AgentTask, ...) 创建独立实例
                     └── 有自己完整的ReAct循环
```
## 准确说法
性质	什么时候用
**Coder（主Agent）**	完整ReAct循环	用户发消息时直接运行
**Title（轻量模型）**	不是ReAct循环，只是 `SendMessages()` 一�	第一次发消息时异步调
**Summarizer（轻量模型）**	不是ReAct循环，只是 `SendMessages()` 一�	用户触发压缩时异步调
**Task（子Agent）**	完整ReAct循环	Coder的AgentTool工具被LLM调用时，才创建
所以：
- **Title 和 Summarizer 不是独立的Agent**——它们只是Coder实例里的两个轻量Provider，调的是简单的单次LLM调用（SendMessages），不走ReAct循环
- **Task 才是真正独立的Agent**——它由Coder运行时通过AgentTool工具启用，有自己完整的ReAct循环和独立Session
我之前的表述"Coder持有3个Provider"在技术上是对的（3个model.Provider），但从架构概念上不准确。应该分两层：
1. **Coder的主Agent** + **两个轻量LLM辅助**（title/summarizer，非ReAct）
2. **AgentTool工具** → 按需创建 **独立的Task Agent**（完整ReAct）
[批注：下面是具体的意见]
----借用他的codeart工作流程，来实现我们的主agent，叫做 univ-task-agent（主agent）
----provider 都采用统一的，不区分
借用 他的 **Summarizer（轻量模型）**
他的Task（子Agent）→ 我们先完全采用，名称换为 read-task-agent，完全采用
[批注]
### 4.5 对标我方可借点

| OpenCode | 我方对应 | 借用策略 |
|----------|---------|---------|
| `BaseTool`接口（Info+Run） | 第3层Tool定义 | **全部采用**：接口规范可借，但我方ArtTool动态生成，非预注册 |
| `ToolInfo{Name, Description, Parameters, Required}` | LLM tool definition JSON Schema | **全部采用**：直接复用 |
| `ToolCall{ID, Name, Input}` / `ToolResponse{Type, Content, IsError}` | LLM调用往返结构 | **全部采用**：直接复用 |
| **SubAgent模式**（agentTool） | **第3层FlowTool** | **全部采用**：FlowTool概念=OpenCode的SubAgent：子Agent + 子Session + 成本归父 |
| Coder vs Task 两套工具列表 | ArtTool（全工具）+ FlowTool（受限工具） | **全部采用**：思路一致，子任务限制工具权限 |
| `permission.Request(sessionID, toolName, action)` | 第4层安全架构HITL | **全部采用**：直接复用权限矩阵模式 |
| 工具查找循环 `for _, availableTool := range a.tools` | 第3层tool dispatch | **全部采用**：直接复用 |

---

### 我的批注（L653-658 具体意见）

----借用他的codeart工作流程，来实现我们的主agent，叫做 univ-task-agent（主agent）
----provider 都采用统一的，不区分
----借用他的 **Summarizer（轻量模型）**
----他的Task（子Agent）→ 我们先完全采用，名称换 read-task-agent，完全采用

---

## 五、Prompt架构（`llm/prompt/`）— ★（直接参考使用）

### 5.1 分派机制

```go
func GetAgentPrompt(agentName config.AgentName, provider models.ModelProvider) string {
    basePrompt := ""
    switch agentName {
    case config.AgentCoder:       basePrompt = CoderPrompt(provider)
    case config.AgentTitle:       basePrompt = TitlePrompt(provider)
    case config.AgentTask:        basePrompt = TaskPrompt(provider)
    case config.AgentSummarizer:  basePrompt = SummarizerPrompt(provider)
    default:                      basePrompt = "You are a helpful assistant"
    }
    // AgentCoder / AgentTask 额外注入项目上下文
    if agentName == AgentCoder || agentName == AgentTask {
        contextContent := getContextFromPaths()
        if contextContent != "" {
            return fmt.Sprintf("%s\n\n# Project-Specific Context\n ... \n%s", basePrompt, contextContent)
        }
    }
    return basePrompt
}
```

### 5.2 CoderPrompt组成（应该参考）

```
CoderPrompt = CoderBasePrompt(provider) + getEnvironmentInfo() + lspInformation()
  ├── baseAnthropicCoderPrompt 或者 baseOpenAICoderPrompt（按provider区分）
  ├── getEnvironmentInfo() → <env>cwd/git/OS/date/ls输出</env>
  └── lspInformation() → LSP diagnostics说明
```

#### 5.2.1 getEnvironmentInfo() 动态注入（需要借用）

```go
// coder.go:170-190
func getEnvironmentInfo() string {
    cwd := config.WorkingDirectory()
    isGit := isGitRepo(cwd)
    platform := runtime.GOOS
    date := time.Now().Format("1/2/2006")  // 美国日期格式
    ls := tools.NewLsTool()
    r, _ := ls.Run(ctx, ToolCall{Input: `{"path":"."}`})
    return `<env>
Working directory: ` + cwd + `
Is directory a git repo: ` + boolToYesNo(isGit) + `
Platform: ` + platform + `
Today's date: ` + date + `
</env>
<project>` + r.Content + `</project>`
}
```

**关键点**：使用 `NewLsTool()` 实时列出当前目录文件作为project上下文，每次调用prompt都重新生成。

#### 5.2.2 项目上下文注入

```go
// prompt.go:15-38
func GetAgentPrompt(agentName, provider) string {
    basePrompt = CoderPrompt(provider)  // 或 TaskPrompt, TitlePrompt, SummarizerPrompt
    if agentName == Coder || agentName == Task {
        contextContent := getContextFromPaths()
        if contextContent != "" {
            return basePrompt + "\n\n# Project-Specific Context\n" + contextContent
        }
    }
    return basePrompt
}

// getContextFromPaths() 读取 config.ContextPaths 中所有文件
// 从 cfg.WorkingDir 开始搜索，同步.Once缓存，并发读取
// 结果格式："# From:" + path + "\n" + content
```

AgentCoder和AgentTask的prompt末尾自动拼接项目上下文文件（如AGENTS.md）。

### 5.3 四种Agent的Prompt对比

| Agent | 有工具？ | 角色 | Prompt长度 |
|-------|---------|------|-----------|
| **Coder** | ✅ 全工具（Bash, Edit, Write, Patch, Glob, Grep, Ls, Sourcegraph, View, Agent等） | 编程助手 | 最长（~200行） |
| **Task** | ✅ 只读工具（Glob, Grep, Ls, Sourcegraph, View） | 搜索/回答问题 | 短（~20行） |
| **Title** | ❌ 无工具 | 生成会话标题（≤50字符） | 极短（~12行） |
| **Summarizer** | ❌ 无工具 | 汇总对话历史 | 短（~16行） |

### 5.4 上下文注入

```go
func getContextFromPaths() string {
    cfg := config.Get()
    // 读 cfg.ContextPaths 中所有文件内容
    // "AGENTS.md" 等 → 拼接为 "# From:path\ncontent"
    // sync.Once 缓存，仅加载一次
}

// 最终prompt = basePrompt + "\n\n# Project-Specific Context\n...\n" + contextContent
```

### 5.5 对标我方可借点

| OpenCode | 我方对应 | 借用策略 |
|---------|---------|---------|
| `GetAgentPrompt`按角色分派 | 第2层构建system message | **直接参考使用**：按意图类型/任务类型分派不同prompt |
| `getContextFromPaths()`读项目文件 | 第3层经验注入 | **直接参考使用**：OpenCode是静态文件，我方是动态经验检索，更灵活 |
| Title/Summarizer独立agent（无工具） | 第3层"单次LLM调用"接口 | **直接参考使用**：标题生成/意图分类等非ReAct场景，走call_complete |
| Coder vs Task 两套prompt | ArtTool（主prompt） | **直接参考使用**：区分可借 |
| `getEnvironmentInfo()`注入环境 | 第2层构建system message时注入环境 | **直接参考使用**：思路一致 |

---

## 六、可直接复用的代码级模式

### 6.1 Cost核算公式

**OpenCode**（Go）：
```go
cost := model.CostPer1MInCached/1e6*float64(usage.CacheCreationTokens) +
    model.CostPer1MOutCached/1e6*float64(usage.CacheReadTokens) +
    model.CostPer1MIn/1e6*float64(usage.InputTokens) +
    model.CostPer1MOut/1e6*float64(usage.OutputTokens)
session.Cost += cost
```

**我方翻译**（Python）：
```python
def calc_cost(model_config: ModelConfig, usage: TokenUsage) -> float:
    cost = (
        model_config.cost_per_1m_in_cached / 1_000_000 * usage.cache_creation_tokens +
        model_config.cost_per_1m_out_cached / 1_000_000 * usage.cache_read_tokens +
        model_config.cost_per_1m_in / 1_000_000 * usage.input_tokens +
        model_config.cost_per_1m_out / 1_000_000 * usage.output_tokens
    )
    return cost
```

### 6.2 权限检查模式

**OpenCode**：
```go
p := b.permissions.Request(permission.CreatePermissionRequest{
    SessionID:   sessionID,
    Path:        config.WorkingDirectory(),
    ToolName:    b.Info().Name,
    Action:      "execute",
    Description: permissionDescription,
    Params:      params.Input,
})
if !p {
    return tools.NewTextErrorResponse("permission denied"), nil
}
```

**我方翻译**：第4层HITL模块中，用 `(session_id, tool_name, action) → bool` 矩阵判断。

### 6.3 子代理成本归父

**OpenCode**：
```go
parentSession.Cost += updatedSession.Cost
_, err = b.sessions.Save(ctx, parentSession)
```

### 6.4 Bash PersistentShell模式

Bash工具不每次spawn新进程，而是维护一个**长连接Shell会话**（`shell/shell.go:18-40`）：

```go
type PersistentShell struct {
    cmd          *exec.Cmd              // 持久化shell进程
    stdin        *os.File               // stdin pipe（命令写入）
    commandQueue chan *commandExecution // goroutine-safe命令队列
}

// 每个命令通过chan提交，串行执行
type commandExecution struct {
    command    string
    timeout    time.Duration
    resultChan chan commandResult  // 结果通过chan返回
    ctx        context.Context
}
```

**特性**：
- `cd`命令跨命令持续有效（状态保持）
- 命令队列防止竞态
- 每个命令独立超时控制
- 支持中断正在执行的命令
- 默认1分钟超时，最大10分钟

### 6.5 Provider创建链（agent → model → provider，我方不区分provider实例）

```go
// agent.go:706-758
func createAgentProvider(agentName) (provider.Provider, error) {
    cfg := config.Get()
    agentConfig := cfg.Agents[agentName]
    model := models.SupportedModels[agentConfig.Model]
    // 统一创建，不区分provider的cache/thinking等特殊处理
}
```

**Agent持有3个Provider实例**（OpenCode的做法，我方不采用——我方只维护一个统一的model实例）：
- `a.provider` — 主Agent推理模型
- `a.titleProvider` — 轻量标题生成模型
- `a.summarizeProvider` — 轻量历史压缩模型

### 6.6 Session busy检查

**OpenCode**：
```go
func (a *agent) IsSessionBusy(sessionID string) bool {
    _, busy := a.activeRequests.Load(sessionID)
    return busy
}
```

**我方翻译**：
```python
class Layer1:
    def __init__(self):
        self._active_tasks: dict[str, asyncio.Task] = {}

    def is_session_busy(self, session_id: str) -> bool:
        return session_id in self._active_tasks
```

### 6.7 Retry + 指数退避 + jitter

**OpenCode源码**（openai.go:337-363）：

```go
func (o *openaiClient) shouldRetry(attempts int, err error) (bool, int64, error) {
    // 仅重试 429(限流) 和 500(服务端错误)
    only 429/500 → continue
    if attempts > maxRetries (8) → return error

    // 优先使用服务端 Retry-After 头
    if Retry-After header exists:
        retryMs = headerValue * 1000  // 秒→毫秒
    else:
        backoffMs = 2000 * 2^(attempts-1)  // 2s, 4s, 8s, 16s...
        jitterMs = backoffMs * 0.2         // +20% jitter

    return true, retryMs
}
```

**核心规则**（我方统一复用，不区分provider）：
- 仅限 HTTP 429（限流）和 500（服务端错误）可重试
- 最大重试次数：8次
- 退避基数：`2000ms * 2^(attempt-1)`（2s→4s→8s→16s→32s→64s→128s→256s）
- Jitter：固定 +20%（绝对值，非随机），非 ±30%
- 若服务端返回 `Retry-After` 头，优先使用服务端指定值

---

## 七、不应借用的部分（差异要点）

| OpenCode的做法 | 我方的理由 |
|---------------|-----------|
| **纯ReAct循环**（while true: LLM→tool→loop） | 原样采用作为execute，plan=轻量级规划agent |
| **每delta写一次DB**（processEvent一次Update DB） | 过于频繁，改为先写内存、流式完成后一次性批量写入DB |
| **静态工具预注册**（CoderAgentTools写死列表） | 第一阶段采用静态注册，第二阶段采用AST动态注册 |
| **Summarize()压缩历史** | 第二阶段采用，功能和功能调用方法采用OpenCode的 |
| **单层Agent架构** | 已重新决策：采用OpenCode的主agent+子agent模式 |
| **Prompt硬编码在Go代码中** | OpenCode的prompt硬编码在Go源码常量中。采用文本文件方式（prompt.md等），运行时加载，结构参考OpenCode拼接方式 |
| **针对特殊provider处理**（Anthropic cache/thinking、Gemini Chat会话等） | 统一的OpenAI兼容模式，所有模型走统一接口 |

---

## 八、前端数据流（PubSub → TUI）（分析后看看情况）

### 8.1 架构概览

OpenCode没有传统REST后端，而是Go TUI（BubbleTea）直接调用核心库。数据和UI之间通过 **泛型PubSub Broker** 解耦：

```
agent/message/session/log/permission
    → 5路 Broker[Event[T]] + goroutine merge
    → 1路 chan tea.Msg
    → program.Send(msg) → BubbleTea事件循环
```

### 8.2 PubSub Broker实现

```go
type Broker[T any] struct {
    subs      map[chan Event[T]]struct{}
    mu        sync.RWMutex
    done      chan struct{}
    subCount  int
    maxEvents int    // 默认1000
}

type Event[T any] struct {
    Type    EventType   // "created" | "updated" | "deleted"
    Payload T
}
```

**核心机制**：
- Publish时**快照订阅列表**（RLock），释放锁后再逐个send
- 每个subscriber是`chan Event[T]`（buffer=64）
- send使用**非阻塞模式**（select default: skip），慢消费者不阻塞publisher
- 通过`ctx.Done()`自动取消订阅

### 8.3 两条数据路径（核心设计）

OpenCode向UI推送数据，实际有**两条独立的路径**：

| 路径 | 触发时机 | Payload类型 | 频率 | UI用途 |
|------|---------|-------------|------|--------|
| **Streaming路径** | 每个ProviderEvent delta → processEvent() → `message.Service.Update()` → Publish(UpdatedEvent) | `message.Message` | 每个text/tool delta一次 | 实时增量渲染 |
| **Completion路径** | Run()结束后 → Publish(CreatedEvent) | `agent.AgentEvent` | 一次 | auto-compact检查、非交互模式返回值 |

**关键规律**：Streaming路径负责**增量更新+实时渲染**，Completion路径只携带**最终状态信号**。两者Payload类型不同（Message vs AgentEvent），通过不同Broker通道到达TUI。

```
Streaming路径（逐字粒度）：
  ProviderEvent{Content: "hel"}
    → agent.AppendContent("hel")
    → message.Service.Update(msg)    ← 修改msg.Parts并更新UpdatedAt
    → Broker[Message].Publish(Updated, msg)
    → TUI messagesCmp: 原地替换message + rerender

Completion路径（一次）：
  Run()返回AgentEvent{Type: "response", Done: true}
    → Broker[AgentEvent].Publish(Created, event)
    → TUI appModel: 仅做auto-compact检查
```

### 8.4 Message CRUD事件

Message Service是Streaming路径的核心，定义了三种CRUD事件：

| 操作 | 事件类型 | 触发时机 |
|------|---------|---------|
| `Create()` | CreatedEvent | 用户发消息、Assistant Message创建 |
| `Update()` | UpdatedEvent | **每个streaming delta**（text/thinking/tool） |
| `Delete()` | DeletedEvent | Session/消息删除 |

UI端 messagesCmp 的处理：

```
CreatedEvent → 追加消息到列表末尾 → scroll到底
UpdatedEvent → 原地替换列表中的消息 → scroll到底
```

### 8.5 核心数据结构：Message.Parts

UI最终渲染的是 `message.Message.Parts []ContentPart` —— 多态有序列表：

```go
type Message struct {
    ID, Role, SessionID  string
    Parts                 []ContentPart   // 多态有序列表
    Model                 models.ModelID
    CreatedAt, UpdatedAt  int64
}

// ContentPart —— 7种具体类型，按type区分
type ContentPart interface { isPart() }

ReasoningContent: { Thinking: string }     // "reasoning" — 思考过程
TextContent:      { Text: string }         // "text"       — 最终文本
ImageURLContent:  { URL, Detail: string }  // "image_url"  — 图片
BinaryContent:    { Path, MIMEType: string; Data: []byte }  // "binary"
ToolCall:         { ID, Name, Input: string; Finished: bool } // "tool_call"
ToolResult:       { ToolCallID, Name, Content: string; IsError: bool } // "tool_result"
Finish:           { Reason: FinishReason; Time: int64 } // "finish"
```

**序列化JSON**：
```json
{
  "id": "msg_xxx",
  "role": "assistant",
  "parts": [
    {"type": "reasoning",  "data": {"thinking": "..."}},
    {"type": "text",       "data": {"text": "Hello world"}},
    {"type": "tool_call",  "data": {"id": "call_1", "name": "Bash", "input": "{}", "finished": true}},
    {"type": "tool_result","data": {"tool_call_id": "call_1", "content": "output", "is_error": false}},
    {"type": "finish",     "data": {"reason": "end_turn", "time": 1712345678}}
  ],
  "model": "claude-sonnet-4-20250514",
  "created_at": 1712345000,
  "updated_at": 1712345678
}
```

**Streaming 建Parts的过程**：

```
1. Message Create
   → Parts = [] (空)

2. ProviderEvent: EventThinkingDelta
   → AppendReasoningContent("thinking text...")
   → Parts = [{type: "reasoning", thinking: "thinking text..."}]
   → Update → Publish(UpdatedEvent)

3. ProviderEvent: EventContentDelta  
   → AppendContent("Hello")
   → Parts = [..., {type: "text", text: "Hello"}]
   → Update → Publish(UpdatedEvent)

4. ProviderEvent: EventToolUseStart
   → AddToolCall({id: "call_1", name: "Bash"})
   → Parts = [..., {type: "tool_call", id: "call_1", ..., finished: false}]
   → Update → Publish(UpdatedEvent)

5. ProviderEvent: EventComplete
   → SetFinish({reason: "end_turn"})
   → Parts = [..., {type: "finish", reason: "end_turn"}]
   → Update → Publish(UpdatedEvent)
```

### 8.6 对我方架构的借鉴价值

| OpenCode | 我方 | 借用策略 |
|----------|------|---------|
| `Broker[T any]` 泛型PubSub | 我方SSE连接管理 | **模式对应**：Go PubSub的subscriber ≈ HTTP SSE connection，Publish ≈ write to response |
| Message.Parts 多态数组 | 我方SSE message事件 | **直接复用数据结构**：type+data的格式完全适合我方SSE的`data: {"type":"text","data":{...}}` |
| Streaming路径 | 我方SSE逐chunk推送 | **思路一致**：每个LLM Chunk推一个SSE事件，前端增量追加 |
| Completion路径 | 我方[complete]信号 | **思路一致**：最后发一个`{"type":"finish"}`标志请求结束 |
| Finish + reason | 我方stop_reason | **直接复用**：end_turn/max_tokens/tool_use/canceled/error |
| CRUD事件（Created/Updated/Deleted） | 我方SSE event类型 | **参考**：可扩展为我方SSE的`event: created/updated/deleted` |

**核心结论**：`Message.Parts` 加 `Created/Updated/Deleted` 事件模型可以直接映射为我方的SSE数据格式。OpenCode用Go泛型Broker解耦的架构，与我方用HTTP SSE + 事件流的思路本质一致，但实现手段不同（Go内存pubsub vs HTTP长连接）。

| 子系统 | 可借性 | 核心可借内容 | 我方位置 |
|--------|-------|-------------|---------|
| Provider接口模式 | ⭐⭐⭐⭐⭐ | Send+Stream双split、事件驱动、retry+backoff | 第4层`llm_client.py` |
| 流式事件类型 | ⭐⭐⭐⭐ | 原样采用10种，事件驱动模式 | 第4层LLMChunk |
| Tool接口规范 | ⭐⭐⭐⭐ | Info/Run/ToolCall/ToolResponse | 第3层工具定义 |
| SubAgent模式 | ⭐⭐⭐⭐⭐ | 子Agent+子Session+成本归父 | 第3层FlowTool |
| 权限控制 | ⭐⭐⭐⭐⭐ | session+tool+action矩阵 | 第4层HITL |
| Cost核算 | ⭐⭐⭐⭐⭐ | CostPer1M * tokens / 1e6 | 第3层usage tracking |
| Session busy检查 | ⭐⭐⭐⭐⭐ | dict[session_id] → cancel | 第1层并发控制 |
| Prompt分派 | ⭐⭐⭐ | 角色→prompt映射 | 第2层system message构建 |
| 上下文注入 | ⭐⭐⭐ | 项目context拼接到prompt | 第3层经验注入 |
| PubSub事件模式 | ⭐⭐⭐⭐⭐ | 泛型Broker非阻塞fan-out | 第1层SSE连接管理 |
| Message.Parts多态数组 | ⭐⭐⭐⭐⭐ | type+data typed content parts | 第1层SSE message格式 |
| 双路径（Streaming+Completion） | ⭐⭐⭐⭐ | 增量更新+最终状态分离 | 第1层SSE推送策略 |
| CRUD事件（Created/Updated/Deleted） | ⭐⭐⭐⭐ | 3种事件类型 | 第1层SSE event type |
| Finish+reason | ⭐⭐⭐⭐⭐ | end_turn/max_tokens/tool_use/canceled/error | 第1层/第4层共用 |
| Provider厂商差异适配 | ❌ | 我方不针对特殊provider处理 | 不采用 |
| ReAct循环 | ⭐⭐⭐⭐⭐ | 原样采用作为execute | 第3层execute step |
| 每delta写DB | ⭐ | 过于频繁，改为先写内存、完成时一次性写入 | 不借 |
| 静态工具注册 | ⭐⭐ | 第一阶段借，第二阶段AST | 第3层（分阶段） |
| 单层Agent | ⭐⭐⭐⭐⭐ | 主Agent+子Agent模式 | 第三层 |

---





## 十一、全部借用策略汇总

> 以下汇总了全文所有带批注章节的借用策略，用段落形式按序号列出，方便查阅。

---

### 一、Provider流式处理体系（二、★★★，第4层参考借用部分）

1. **Provider接口双split** 
    ：OpenCode的Provider接口分成SendMessages（非流式）和StreamResponse（流式）两套方法。我方对应llm_client.py的call_complete()和call_stream()。策略是参考借用，第4层复用接口split模式。

2. **ProviderEvent事件体系（原样采用）**：OpenCode定义了10种事件类型。我方对应LLMChunk事件。策略是原样采用10种事件类型，不精简为5种。[问题:我们的为什么是chunk的5种事件---看起来不对?]

3. **ChatCompletionAccumulator**：
    OpenCode用accumulator在流式过程中拼接arguments chunks，这是tool calling流式的标准解法。策略是直接复用思路。

4. **指数退避+shouldRetry**：
  OpenCode的Go版本有shouldRetry判断逻辑。我方对应_retry_with_backoff()。策略是直接复制算法，把Go的shouldRetry翻译为Python版本。

5. **NewProvider工厂+providerClientOptions**：
  OpenCode用Option模式初始化provider。我方对应LLMConfig从config.yaml加载。策略是参考借用，但Go用Option模式，我方用Pydantic config。

6. **ForEach provider分派**：OpenCode遍历所有provider执行stream()。我方对应llm_client.py按provider分派。策略是参考借用。[问题:我们不是一个可用provider吗?选择好了即可?不是吗]


---

### 二、Agent ReAct核心循环（三、★★，第三层-全部采用）

7. **纯ReAct循环（原样采用）**：OpenCode是while toolUse→loop的纯ReAct。我方是Plan→Execute两步。策略是原样采用这个主要loop作为我们的execute，而我们的plan是一个轻量级的agent——进行任务规划的agent。[批注:原样采用这个主要的loop,=我们的execute,而我们的plan是一个轻量级的agent-进行任务规划的agent]

8. **activeRequests按session隔离（逻辑原理原样采用）**：OpenCode用sync.Map做activeRequests，按session隔离。我方对应第1层_active_tasks: dict[str, asyncio.Task]。策略是逻辑原理原样采用：直接复用设计，Go的sync.Map对应Python的dict。

9. **IsSessionBusy检查（逻辑原理原样采用）**：OpenCode有IsSessionBusy方法。我方对应_is_session_busy()。策略是逻辑原理原样采用：直接复用。

10. **SummaryMessageID截断历史（逻辑原理原样采用）**：OpenCode用SummaryMessageID标记截断点。我方对应第2层context window管理。策略是逻辑原理原样采用：用summary标记截断点，比纯滑动窗口更智能。

11. **processEvent 10种事件实时写DB（逻辑原理原样采用）**：OpenCode在流式过程中对每种事件调用processEvent写DB。我方对应SSE流式过程中写DB。策略是逻辑原理原样采用：但每delta写太频繁，我方优化为批量或checkpoint写。

12. **TrackUsage cost核算（逻辑原理原样采用）**：OpenCode在agent层做cost核算。我方对应token usage tracking。策略是逻辑原理原样采用：公式可直接复制。

13. **Provider热切换（自行设计）**：OpenCode通过agent.Update()重建provider实现热切换。我方对应模型切换。策略是自行设计，在配置文件选好即可，不热切换。

---

### 三、核心接口与SubAgent（批注"全部采用"——在我们的第三层）

14. **BaseTool接口（Info+Run）**：OpenCode每个工具实现Info和Run两个方法。我方对应第3层Tool定义。策略是全部采用：接口规范可借，但我方ArtTool是动态生成，非预注册。

15. **ToolInfo（Name、Description、Parameters、Required）**：OpenCode用ToolInfo结构体描述工具。我方对应LLM tool definition JSON Schema。策略是全部采用：直接复用。

16. **ToolCall/ToolResponse**：OpenCode用ToolCall{ID, Name, Input}和ToolResponse{Type, Content, IsError}表示LLM调用往返。策略是全部采用：直接复用。

17. **SubAgent模式（agentTool）**：OpenCode的agentTool是一个AgentTool，内部封装子Agent+子Session。我方对应第3层FlowTool。策略是全部采用：FlowTool概念=OpenCode的SubAgent，即子Agent+子Session+成本归父。

18. **Coder vs Task两套工具列表**：OpenCode中Coder和Task有不同的可用工具列表。我方对应ArtTool（全工具）+ FlowTool（受限工具）。策略是全部采用：思路一致，子任务限制工具权限。

19. **permission.Request权限控制**：OpenCode用permission.Request(sessionID, toolName, action)做权限检查。我方对应第4层安全架构HITL。策略是全部采用：直接复用权限矩阵模式。

20. **工具查找循环**：OpenCode遍历tools列表查找匹配的工具名。策略是全部采用：直接复用。

---

### 四、工具实现模式批注

21. **各工具实现模式（Info+Run）**：各工具都实现Info+Run接口。策略是第1版采用此方法——我们第2版采用AST注册（不写死列表）。

---

### 五、子agent的技术

22. **借用codeart工作流程**：实现我们的主agent，主agent名字叫做univ-task-agent。

23. **Provider统一**：不区分多种Provider，统一用一个Provider接口。

24. **借用Summarizer（轻量模型）**：用轻量模型压缩历史。

25. **Task（子Agent）完全采用**：名称换为read-task-agent。

---

### 六、Prompt架构（五、★，直接参考使用）

26. **GetAgentPrompt按角色分派**：OpenCode根据Agent角色（Coder/Task等）返回不同prompt。我方对应第2层构建system message。策略是直接参考使用：按意图类型/任务类型分派不同prompt。

27. **getContextFromPaths读项目文件**：OpenCode读取项目相关文件拼接到prompt。我方对应第3层经验注入。策略是直接参考使用：OpenCode是静态文件，我方是动态经验检索，更灵活。

28. **Title/Summarizer独立agent（无工具）**：OpenCode中Title和Summarizer是独立agent但没有工具。我方对应第3层"单次LLM调用"接口。策略是直接参考使用：标题生成/意图分类等非ReAct场景，走call_complete。

29. **Coder vs Task两套prompt**：OpenCode有两套prompt模板。我方对应ArtTool（主prompt）。策略是直接参考使用：区分可借。

30. **getEnvironmentInfo()注入环境**：OpenCode在prompt中动态注入环境信息。我方对应第2层构建system message时注入环境。策略是直接参考使用：思路一致。

---

### 七、Prompt组成批注

31. **5.2 CoderPrompt组成**：批注"应该参考"。策略是应该参考OpenCode的CoderPrompt组成方式。

32. **5.2.1 getEnvironmentInfo()动态注入**：批注"需要借用"。策略是需要借用。

---

### 八、不应借用的部分（第七章）

33. **每delta写一次DB**：过于频繁，改为checkpoint/批量写（具体方案待研究确认）。[问题:我不知道哪个好，或者合理?需要研究确认我们的模式是不是合理的?]

34. **静态工具预注册**：第一阶段采用静态注册（也就是现在的阶段），第二阶段采用AST动态注册。

35. **Summarize()压缩历史**：第二阶段采用，功能和功能调用方法也是采用OpenCode的。

36. **单层Agent架构**：[批注：我方四层分离，第2层task编排+前置，第3层独立执行，职责更清晰。---这些说明有问题，下面是我的决定] 这个重新决策：采用OpenCode的模式——主agent + 子agent的模式。

37. **Prompt硬编码在Go代码中**：OpenCode的prompt是硬编码在Go源码常量中的（`const baseOpenAICoderPrompt = \`...\``）。[批注]还是准确弄明白OpenCode的prompt是怎么写的、怎么设置的——OpenCode结构是basePrompt(provider区分) + getEnvironmentInfo() + lspInformation() + getContextFromPaths()四层拼接。[问题]我方用配置文件+模板方式，不在源码硬编码——这个是我们老系统的方法，效果非常差，基本上不能实现复杂的任务，所以老系统的方法不能采用。[决定]采用文本文件方式（prompt.md等）存储prompt，运行时加载，结构参考OpenCode的拼接方式。

38. **同步模型切换只改config+recreate provider**：[问题]这个我没有看到——一样的方法，实际采用了。应该是小功能点吧?

39. **针对特殊provider处理**：统一的OpenAI兼容模式，所有模型走统一接口，不针对特殊provider处理。

---

### 九、最终子系统可借性总评

41. **Provider接口模式（⭐⭐⭐⭐⭐）**：Send+Stream双split、事件驱动、retry+backoff。对应我方第4层llm_client.py。

42. **流式事件类型（⭐⭐⭐⭐）**：10→5精简，事件驱动模式。对应我方第4层LLMChunk。

43. **Tool接口规范（⭐⭐⭐⭐）**：Info/Run/ToolCall/ToolResponse。对应我方第3层工具定义。

44. **SubAgent模式（⭐⭐⭐⭐⭐）**：子Agent+子Session+成本归父。对应我方第3层FlowTool。

45. **权限控制（⭐⭐⭐⭐⭐）**：session+tool+action矩阵。对应我方第4层HITL。

46. **Cost核算（⭐⭐⭐⭐⭐）**：CostPer1M * tokens / 1e6。对应我方第3层usage tracking。

47. **Session busy检查（⭐⭐⭐⭐⭐）**：dict[session_id] → cancel。对应我方第1层并发控制。

48. **Prompt分派（⭐⭐⭐）**：角色→prompt映射。对应我方第2层system message构建。

49. **上下文注入（⭐⭐⭐）**：项目context拼接到prompt。对应我方第3层经验注入。

50. **PubSub事件模式（⭐⭐⭐⭐⭐）**：泛型Broker非阻塞fan-out。对应我方第1层SSE连接管理。

51. **Message.Parts多态数组（⭐⭐⭐⭐⭐）**：type+data typed content parts。对应我方第1层SSE message格式。

52. **双路径（Streaming+Completion）（⭐⭐⭐⭐）**：增量更新+最终状态分离。对应我方第1层SSE推送策略。

53. **CRUD事件（Created/Updated/Deleted）（⭐⭐⭐⭐）**：3种事件类型。对应我方第1层SSE event type。

54. **Finish+reason（⭐⭐⭐⭐⭐）**：end_turn/max_tokens/tool_use/canceled/error。对应我方第1层/第4层共用。

55. **Provider厂商差异适配（❌不采用）**：我方不针对特殊provider处理。

56. **ReAct循环（⭐不借）**：我方用Plan→Execute。

57. **每delta写DB（⭐不借）**：过于频繁。

58. **静态工具注册（⭐第一阶段借，第二阶段不借）**：第一阶段静态注册，第二阶段AST动态生成。

59. **单层Agent（⭐⭐⭐⭐⭐主Agent+子Agent模式，改为采用）**：原决定"不借"，现已重新决策为采用OpenCode的主agent+子agent模式。
