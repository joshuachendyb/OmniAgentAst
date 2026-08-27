# Action / Observation 渲染链路分析报告

| 版本 | 时间 | 签名 | 修改简介 |
|------|------|------|---------|
| v1.0 | 2026-08-27 15:34:17 | 小欧 | 新建：action/observation 前端渲染链路完整分析 |
| v1.1 | 2026-08-27 15:47:02 | 小欧 | 补充：observation数据渲染时机说明、GenericResultRenderer细节、页面显示样式图 |

**创建时间**：2026-08-27 15:34:17
**编写人**：小欧

---

## 一、Action 步骤渲染链路

### 1.1 SSE 解析层

**文件**：`frontend/src/utils/sse.ts:1670-1765`

后端发送 action 事件，前端解析后生成以下数据结构：

```typescript
{
  type: 'action',
  step: number,
  timestamp: number,
  exec_type: 'single' | 'multi',
  tools: Array<{
    tool: string,        // 工具名
    target?: string,     // 目标路径（可选）
    params?: Record<string, unknown>  // 参数
  }>,
  content?: string,      // 自动生成: tools.map(t => t.target ? `${t.tool}(${t.target})` : t.tool).join(' + ')
  tool_name?: string,
  tool_params?: Record<string, unknown>,
  execution_status?: 'success' | 'error' | 'warning',
  summary?: string,
  execution_result?: Record<string, unknown> | null,
  execution_time_ms?: number,
  action_retry_count?: number
}
```

**解析逻辑关键点**：
- 后端发送 `exec_type: 'single' | 'multi'` 和 `tools` 数组（`sse.ts:1675-1693`）
- `content` 由前端自动生成，格式为 `工具名(目标) + 工具名2`（`sse.ts:1694-1696`）
- 保存到 `executionSteps` 并调用 `onStep` 回调（`sse.ts:1711-1754`）

### 1.2 分类层

**文件**：`frontend/src/components/Chat/pipeline/steps.ts:39-47`

```typescript
export const META_STEP_TYPES = [
  'start', 'startinfo', 'paused', 'resumed', 'retrying',
  'usage', 'stats', 'final_stats', 'context_overview', 'truncated',
] as const;

export const isBusinessStep = (s: ExecutionStep): boolean =>
  !(META_STEP_TYPES as readonly string[]).includes(s.type);
```

**分类结果**：action 不在 META_STEP_TYPES 中，是 **business 步骤**，进入右侧查看区流水线。

### 1.3 PipelineRenderer 段构建

**文件**：`frontend/src/components/Chat/pipeline/PipelineRenderer.tsx:48-50`

```typescript
case 'action':
  segs.push({ kind: 'tool', action: s, observations: [] });
  break;
```

**段类型**：`{ kind: 'tool', action: ExecutionStep, observations: ExecutionStep[] }`

每个 action 创建一个 tool 段，observations 数组初始为空，等待后续 observation 追加。

### 1.4 ToolCallLine 渲染

**文件**：`frontend/src/components/Chat/pipeline/ToolCallLine.tsx:24-95`

**Props**：
```typescript
interface ToolCallLineProps {
  action: ExecutionStep;
  observations?: ExecutionStep[];
  highlight?: boolean;  // HITL 联动高亮
}
```

**收起态显示**（:61-74）：

| 元素 | 内容 | 代码位置 |
|------|------|---------|
| 工具图标 | `🔧` | :62 |
| 工具名 | `tools.map(t => t.tool).join(', ')` | :38 |
| 重试标签 | `action_retry_count > 0` 时显示 `(重试N)` | :46-47 |
| 参数摘要 | `JSON.stringify(params).slice(0, 60)` + `...` | :65-66 |
| 结果摘要 | 优先 `obs0.summary` → `obs0.content` → `[工具结果]` | :41-44 |
| 展开按钮 | `▲`/`▼` | :71-73 |

**收起态完整示例**：
```
🔧 read_file(C:\config.json) 参数：{"path":"C:\config.json"} → 文件内容摘要 ▼
```

**展开态显示**（:75-92）：

| 元素 | 内容 | 代码位置 |
|------|------|---------|
| 完整参数 | `CollapsibleText` 组件 | :78 |
| 观察结果 | 遍历 `observations` 数组，每个显示 `观察N：` | :79-90 |
| 字符串结果 | `CollapsibleText` | :84-85 |
| 对象结果 | `ToolResultRenderer` 工厂组件 | :86-87 |

### 1.5 observation 数据渲染时机说明

**关键问题**：action 步骤在后端 yield 时还没有执行结果，收起态显示的"结果摘要"数据从哪来？

**答案**：数据来自后续的 observation 步骤，在 `buildSegments` 阶段已完成配对。

**时序说明**：
```
1. SSE 收到 action → executionSteps = [action₁]
2. SSE 收到 observation → executionSteps = [action₁, observation₁]
3. buildSegments 遍历所有 steps：
   - action₁ → 创建 tool 段，observations=[]
   - observation₁ → 前一个是 tool 段，追加到 observations=[observation₁]
4. ToolCallLine 渲染时，observations 数组已有 observation₁ 的数据
```

**结论**：收起态的"结果摘要" = 后续 observation 的 `summary`/`content`，不是 action 自身的数据。这是正确的设计——用户看到 `🔧 工具名 → 结果摘要` 是完整的工具调用信息。

### 1.6 历史回放渲染

**文件**：`frontend/src/components/Chat/right/RightViewer.tsx:108-116`

```typescript
const displaySteps = isCurrentLive ? liveSteps : historySteps;

<PipelineRenderer
  steps={splitSteps(displaySteps).business}
  streaming={isCurrentLive}
  highlightToolName={highlightToolName}
/>
```

**逻辑**：
- 实时任务：使用 `liveSteps`（SSE 流式数据）
- 历史任务：从 `executionApi.getTaskSteps(activeTaskId)` 获取（:65-84）
- 两者都经过 `splitSteps().business` 过滤，走相同的 PipelineRenderer 渲染

---

## 二、Observation 步骤渲染链路

### 2.1 SSE 解析层

**文件**：`frontend/src/utils/sse.ts:1769-1871`

后端发送 observation 事件，前端解析后生成以下数据结构：

```typescript
{
  type: 'observation',
  step: number,
  timestamp: number,
  code?: string,              // SUCCESS/ERROR/WARNING
  observation?: ObservationData | string,  // 原始数据
  tool_result?: unknown,      // 新字段：工具结果数组
  tool_name?: string,
  tool_params?: Record<string, unknown>,
  summary?: string,
  content?: string,           // 用于前端显示
  execution_status?: 'success' | 'error' | 'warning',
  error_message?: string,
  return_direct?: boolean,
  parallel_results?: Array<{
    tool_name: string,
    tool_params: Record<string, unknown>,
    llm_data: Record<string, unknown>,
    tool_result: unknown,
    other_data: Record<string, unknown>
  }>
}
```

**解析逻辑关键点**（:1782-1856）：

1. **新格式（Phase 2）**：`observation` 是 JSON 对象，含 `llm_data/tool_result/other_data`
   - `llm_data` 是数组（单工具 `[dict]`，多工具 `[dict1,dict2]`），取首项（:1806-1808）
   - 字段映射：`llm_data[0].summary` → `step.summary`，`llm_data[0].action.tool` → `step.tool_name`
   - `tool_result` 直接赋值给 `step.tool_result`（:1815）
   - `other_data.return_direct` → `step.return_direct`

2. **旧格式兼容**：`observation` 是字符串或 null/undefined（:1848-1856）

### 2.2 分类层

**文件**：`frontend/src/components/Chat/pipeline/steps.ts:39-47`

**分类结果**：observation 不在 META_STEP_TYPES 中，是 **business 步骤**。

### 2.3 PipelineRenderer 段构建

**文件**：`frontend/src/components/Chat/pipeline/PipelineRenderer.tsx:51-55`

```typescript
case 'observation': {
  const last = segs[segs.length - 1];
  if (last && last.kind === 'tool') last.observations.push(s);
  else segs.push({ kind: 'obs', step: s });  // 孤儿观察
  break;
}
```

**两种情况**：

| 条件 | 段类型 | 说明 |
|------|-------|------|
| 前一个是 `tool` 段 | `tool.observations` 数组 | 内联到 ToolCallLine |
| 前一个不是 `tool` 段 | `{ kind: 'obs', step }` | 孤儿观察，独立显示 |

### 2.4 配对显示逻辑

**action-observation 配对机制**：

```
action₁ → observation₁ → observation₂ → action₂ → observation₃
   ↓           ↓              ↓            ↓           ↓
 tool₁      tool₁.         tool₁.        tool₂      tool₂.
            observations   observations             observations
            [obs₁]         [obs₁,obs₂]              [obs₃]
```

**配对规则**：
1. 每个 `action` 创建一个新 `tool` 段，`observations` 数组初始为空
2. 后续的 `observation` 如果前一个是 `tool` 段，就追加到该 `tool.observations` 数组
3. 如果前一个不是 `tool` 段，该 observation 成为孤儿观察

**多个 observation 处理**：
- 多个 observation 会按顺序追加到同一个 `tool.observations` 数组（:53）
- 在 ToolCallLine 展开态中遍历显示（:79-90）

### 2.5 内联显示细节（展开态）

**文件**：`frontend/src/components/Chat/pipeline/ToolCallLine.tsx:79-90`

```typescript
{observations.map((o, idx) => (
  <div key={idx} style={{ marginTop: 6, paddingLeft: 12 }}>
    <div style={{ color: '#8c8c8c', marginBottom: 4 }}>观察{idx + 1}：</div>
    {typeof o.content === 'string' ? (
      <CollapsibleText text={o.content} />
    ) : (
      <ToolResultRenderer step={o} />
    )}
  </div>
))}
```

**显示逻辑**：
- 遍历 `observations` 数组，每个显示 `观察N：`
- 字符串结果 → `CollapsibleText`（:84-85）
- 对象结果 → `ToolResultRenderer` 工厂（:86-87）

### 2.6 ToolResultRenderer 工厂

**文件**：`frontend/src/components/Chat/ToolResultRenderer/index.tsx:43-107`

**数据读取优先级**：
```typescript
// 优先 tool_result（新字段）
if (step.tool_result !== undefined && step.tool_result !== null) {
  return <DefaultRenderer step={step} />;
}

// 其次按 tool_name 选择专用渲染器
switch (step.tool_name) {
  case "listdir": return <ListDirectoryRenderer step={step} />;
  case "readtext": return <ReadFileRenderer step={step} />;
  // ... 其他工具
  default: return <DefaultRenderer step={step} />;
}
```

### 2.7 GenericResultRenderer 智能渲染

**文件**：`frontend/src/components/Chat/renderers/GenericResultRenderer.tsx:35-131`

DefaultRenderer 将 `tool_result` 数据交给 `GenericResultRenderer` 智能渲染，不是直接显示原始 JSON。

**渲染规则**：

| 数据类型 | 渲染方式 | 代码位置 |
|---------|---------|---------|
| **字符串** | 短文本(≤100字)直接显示；长文本(>100字)折叠(2行+展开) | :40-60 |
| **数组** | 短数组(≤5项且非对象)用 `Tag` 展示；长数组嵌套渲染 | :66-98 |
| **对象** | ≤3个key 用 flex 布局；>3个key 用 `Descriptions` 组件 | :100-127 |
| **图片** | 自动识别 `data:image` 或图片URL，用 `Image` 组件 | :42-48 |
| **null/undefined** | 显示 `-` | :36-38 |

**色彩方案**：使用9种浅色方案（禁止深色背景），按 depth 轮换：
```typescript
const colorSchemes = [
  { bg: '#f0f0f0', border: '#1890ff' },  // 默认
  { bg: '#E6F7FF', border: '#1890FF' },  // 蓝色
  { bg: '#FFF7E6', border: '#FA8C16' },  // 橙色
  { bg: '#F6FFED', border: '#52C41A' },  // 绿色
  // ... 共9种
];
```

**示例渲染效果**：
```
输入: { name: "config.json", size: 1024, content: "..." }

输出（≤3个key）:
  name: config.json    size: 1024    content: ...（折叠）

输入: [{tool: "read", status: "ok"}, {tool: "write", status: "ok"}]

输出（短数组）:
  [read] [write]  ← Tag 展示

输入: { files: ["a.txt", "b.txt", ...], count: 10 }

输出（>3个key）:
  ┌──────────┬────────────────────┐
  │ files    │ a.txt, b.txt, ...  │
  │ count    │ 10                 │
  └──────────┴────────────────────┘
```

### 2.9 孤儿观察渲染

**文件**：`frontend/src/components/Chat/pipeline/PipelineRenderer.tsx:127-136`

```typescript
if (seg.kind === 'obs') {
  return (
    <div style={{ color: '#52c41a', fontSize: 13, margin: '4px 0' }}>
      📋 {seg.step.summary || seg.step.content || ''}
    </div>
  );
}
```

**显示内容**：优先 `summary`，其次 `content`，显示为绿色弱化行。

**何时出现孤儿观察**：
- **正常流程不会出现**：后端总是先 yield action 再 yield observation
- **仅在异常情况出现**：
  1. 历史回放数据不完整（action 步骤丢失）
  2. SSE 流中断后重连，observation 先到
  3. 后端 bug 导致 observation 没有对应的 action
- **这是防御性设计**，正常流程不会触发

### 2.10 历史回放渲染

与 action 相同，走 `RightViewer → splitSteps → PipelineRenderer` 链路（RightViewer.tsx:108-116）。

---

## 三、关键问题总结

| 问题 | 答案 | 代码引用 |
|------|------|---------|
| **action 和 observation 如何配对？** | `buildSegments` 中 observation 检查前一个 segment 是否为 `tool`，是则追加到 `tool.observations`，否则成为孤儿观察 | PipelineRenderer.tsx:51-55 |
| **observation 结果如何嵌入 ToolCallLine？** | 展开态遍历 `observations` 数组，用 `ToolResultRenderer` 工厂组件渲染 | ToolCallLine.tsx:79-90 |
| **多个 observation 如何处理？** | 按顺序追加到同一个 `tool.observations` 数组，展开时逐个显示（标签为"观察1"、"观察2"...） | ToolCallLine.tsx:82 |
| **observation 的 tool_result 数据来源？** | SSE 解析时从 `observation.tool_result` 提取，赋值给 `step.tool_result` | sse.ts:1815 |
| **ToolResultRenderer 选择逻辑？** | 优先检查 `step.tool_result`（新字段），有则用 `DefaultRenderer`；否则按 `step.tool_name` 选择专用渲染器 | ToolResultRenderer/index.tsx:54-107 |
| **收起态的"结果摘要"数据从哪来？** | 来自后续 observation 的 `summary`/`content`，在 `buildSegments` 阶段已完成配对，不是 action 自身的数据 | ToolCallLine.tsx:41-44 |
| **孤儿观察什么时候出现？** | 正常流程不会出现（后端总是先 action 后 observation），仅在历史回放数据不完整或 SSE 流中断重连时出现 | PipelineRenderer.tsx:54 |
| **observation 显示原始 JSON 吗？** | 不是，GenericResultRenderer 会智能渲染：字符串折叠、数组用Tag、对象用Descriptions，不是直接显示原始 JSON | GenericResultRenderer.tsx:35-131 |

---

## 四、数据流全景图

```
SSE 流
  ↓
processSSEData (sse.ts:1141)
  ├─ case 'action' → ExecutionStep { type:'action', tools:[], exec_type:'single'|'multi' }
  └─ case 'observation' → ExecutionStep { type:'observation', tool_result, summary, tool_name }
  ↓
useSSE → executionSteps (React state)
  ↓
useChatStreaming → executionSteps
  ↓
NewChatContainer → liveSteps={executionSteps}
  ↓
RightViewer
  ├─ isCurrentLive ? liveSteps : historySteps (REST API)
  └─ splitSteps(displaySteps).business
  ↓
PipelineRenderer
  └─ buildSegments(steps)
       ├─ 'action' → { kind:'tool', action, observations:[] }
       └─ 'observation' → 追加到前一个 tool.observations 或 { kind:'obs' }
  ↓
渲染:
  ├─ kind:'tool' → ToolCallLine (收起/展开)
  │    └─ 展开态 → ToolResultRenderer (工厂模式)
  │         └─ DefaultRenderer → GenericResultRenderer (智能渲染)
  └─ kind:'obs' → 孤儿观察行 (📋 + summary)
```

---

## 五、页面显示样式

### 5.1 右侧消息查看区 - 实时任务

```
┌─────────────────────────────────────────────────────────────────┐
│  💬 read_file                                                  │
│  参数：{"path":"C:\\config.json"}...                            │
│  → 文件配置内容已读取                                            │
│  ▼                                                              │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 参数：                                                      │ │
│ │ {"path":"C:\\config.json","encoding":"utf-8"}               │ │
│ │                                                             │ │
│ │ 观察：                                                      │ │
│ │ {"status":"success","content":"{\n  \\"name\\": \\"test\\" │ │
│ │ ...\n}","size":1024}                                        │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  💬 write_file                                                 │
│  参数：{"path":"C:\\output.txt","content":"..."}               │
│  → 文件写入成功                                                │
│  ▼                                                              │
├─────────────────────────────────────────────────────────────────┤
│  🤔 正在思考...                                                 │
├─────────────────────────────────────────────────────────────────┤
│  根据分析结果，我已完成配置文件的修改...                           │
│  文件已成功写入，内容包含...                                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 任务统计                                                 │   │
│  │ 状态：✅ completed    总耗时：12s                        │   │
│  │ 步骤/轮次：4 / 2       重试：0                          │   │
│  │ 工具：read_file、write_file                              │   │
│  │ token：P 1234 / C 567 / T 1801                          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 右侧消息查看区 - 收起态

```
┌─────────────────────────────────────────────────────────────────┐
│  🔧 read_file(C:\config.json) 参数：{"path":"C:\\config.json"... → 文件配置内容已读取 ▼  │
├─────────────────────────────────────────────────────────────────┤
│  🔧 write_file 参数：{"path":"C:\\output.txt","content":"... → 文件写入成功 ▼            │
├─────────────────────────────────────────────────────────────────┤
│  🤔 正在思考...                                                 │
├─────────────────────────────────────────────────────────────────┤
│  根据分析结果，我已完成配置文件的修改...                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 右侧消息查看区 - HITL 高亮态

```
┌─────────────────────────────────────────────────────────────────┐
│  🔧 delete_file 参数：{"path":"C:\\temp\\old.txt"}             │
│  → ⚠️ 需要确认                                                │
│  ▼                                                              │
│ ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐ │
│  参数：{"path":"C:\\temp\\old.txt"}                            │
│ │                                                             │ │
│  观察：                                                        │
│ │ ⚠️ 等待用户确认...                                          │ │
│ └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘ │
│  （橙色呼吸边框 + 浅橙背景）                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 左侧任务列表

```
┌─────────────────┐
│ 📋 会话任务      │
├─────────────────┤
│ ▶ 会话（续聊）   │ ← 蓝色左边框选中
│   12:34 已完成   │
├─────────────────┤
│   独立（新任务）  │
│   12:30 已完成   │
├─────────────────┤
│   会话（续聊）    │
│   12:28 执行中   │
├─────────────────┤
│                  │
│                  │
├─────────────────┤
│ 底部信息区        │
└─────────────────┘
```

### 5.5 任务信息条

**主行（收起态）**：根据任务状态显示不同的 Badge，其他信息固定显示。

```
┌─────────────────────────────────────────────────────────────────┐
│  ⏳ 执行中  耗时 12s  步骤 4 / 轮次 2  本轮/任务 token 1801    │
│  上下文 2048tok                                         展开 ▼  │
└─────────────────────────────────────────────────────────────────┘
```

**状态 Badge 对应表**：

| 任务状态 | Badge 显示 | 图标 |
|---------|-----------|------|
| 执行中 | `⏳ 执行中` | processing |
| 已暂停 | `⏸️ 已暂停` | warning |
| 已完成 | `✅ 已完成` | success |
| 失败 | `❌ 失败` | error |
| 已取消 | `🚫 已取消` | default |
| 待命 | `○ 待命` | default |

**展开态**：显示过程事件历史

```
┌─────────────────────────────────────────────────────────────────┐
│  ⏳ 执行中  耗时 12s  步骤 4 / 轮次 2  本轮/任务 token 1801    │
│  上下文 2048tok                                         收起 ▲  │
├─────────────────────────────────────────────────────────────────┤
│  ▶️ 任务已开始 12:30:01                                         │
│  ⏸️ 任务已暂停 12:30:15                                         │
│  ▶️ 任务已恢复 12:30:20                                         │
└─────────────────────────────────────────────────────────────────┘
```

**Token 显示说明**：
- 主显示：`本轮/任务 token {total}`（总 token 数）
- 悬浮提示：`P {prompt_tokens} / C {completion_tokens}`（提示/完成 token 分开）
- 数据结构：`{ prompt: number, completion: number, total: number }`

### 5.6 输入区

```
┌─────────────────────────────────────────────────────────────────┐
│  [ ] 续聊任务                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 请输入消息...                                                │ │
│ │                                                             │ │
│ │                                                             │ │
│ └─────────────────────────────────────────────────────────────┘ │
│  [📎 附件]                    [🚀 发送] [⏹ 停止] [⏸ 暂停]      │
└─────────────────────────────────────────────────────────────────┘
```

### 5.7 顶栏区

```
┌─────────────────────────────────────────────────────────────────┐
│ ← 会话标题                    任务: 3  token: 12345       │
└─────────────────────────────────────────────────────────────────┘
```

**Token 显示**：顶栏显示会话累计 token（所有任务的 token 总和），悬浮提示显示 P/C/T 三组数字。

---

**编写人**：小欧
**时间**：2026-08-27 15:47:02
