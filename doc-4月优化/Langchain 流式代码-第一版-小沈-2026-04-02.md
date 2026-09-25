# LangChain 流式输出代码

**文档版本**: v1.0
**创建时间**: 2026-04-02 22:44:02
**编写人**: 小沈
**存放位置**: D:\OmniAgentAs-desk\doc-react步骤\
**来源**: 从 LangChain-ReAct-学习报告-补充-小沈-2026-04-02 copy.md 第16.3节提取

---

## 1 LangGraph 流式事件机制

**来源**: LangGraph 官方文档 2026-03-10

LangGraph 提供三种流式模式：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `astream()` | 每个节点完成后输出完整结果 | 查看中间状态 |
| `astream_events()` | 节点内部的 token 级事件 | **实时 token 流式输出** |
| `astream_log()` | 完整运行日志 | 调试 |

---

## 2 核心代码

**来源**: LangGraph 官方示例

```python
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from typing import TypedDict

//第1步：定义状态
class AgentState(TypedDict):
    messages: list
    response: str

# 第2步：创建 LLM（必须 streaming=True）
# 为什么需要？
//普通 LLM：await llm.invoke(messages) → 等全部生成完才返回
//流式 LLM：streaming=True → 每生成一个 token 就yield出来


llm = ChatOpenAI(model="gpt-4o", streaming=True)

 //第3步：定义节点函数   作用：这个函数就是"处理用户消息"的逻辑。
def chat_node(state: AgentState) -> AgentState:
    # state 来自上一个节点（这里只有一轮，直接用输入）
    response = llm.invoke(state["messages"])
    # 返回新的状态
    return {"response": response.content}
//第4步：构建图
builder = StateGraph(AgentState)
builder.add_node("chat", chat_node)
builder.set_entry_point("chat")
builder.add_edge("chat", END)
graph = builder.compile()

# 第5步：流式输出（核心！）流式输出
async def stream_tokens(user_input: str):
    inputs = {"messages": [{"role": "user", "content": user_input}]}
    
    async for event in graph.astream_events(inputs, version="v2"):
        kind = event["event"]
        
        # 只过滤 token 级事件
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            token = chunk.content  # 单个 token
            if token:
                yield token
```

---

## 3 事件字段说明

| 字段 | 值 | 含义 |
|------|-----|------|
| `event` | `on_chat_model_stream` | Token 到达 |
| `name` | 节点名称（如 `"chat"`） | 哪个节点发出的 |
| `data["chunk"].content` | `"Hello"` | 实际的 token 文本 |

---

## 4 工具调用（Tool Call）事件处理

**来源**: LangGraph 官方文档 2026-03-10

当 Agent 需要调用外部工具时，会触发两类事件：
- `on_tool_start`：工具开始执行
- `on_tool_end`：工具执行完成

### 4.1 完整代码示例

```python
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from typing import TypedDict

# 第1步：定义工具
@tool
def get_weather(city: str) -> str:
    """获取城市天气"""
    return f"{city} 天气：晴，25°C"

# 第2步：定义状态
class AgentState(TypedDict):
    messages: list
    response: str

# 第3步：创建带工具的 LLM
llm = ChatOpenAI(model="gpt-4o", streaming=True)
llm_with_tools = llm.bind_tools([get_weather])

# 第4步：定义节点（带工具调用逻辑）
def chat_node(state: AgentState) -> AgentState:
    messages = state["messages"]
    # LLM 会自动判断是否需要调用工具
    response = llm_with_tools.invoke(messages)
    return {"response": str(response)}

# 第5步：构建图
builder = StateGraph(AgentState)
builder.add_node("chat", chat_node)
builder.set_entry_point("chat")
builder.add_edge("chat", END)
graph = builder.compile()

# 第6步：流式输出（包含工具调用事件！）
async def stream_with_tools(user_input: str):
    inputs = {"messages": [{"role": "user", "content": user_input}]}
    
    async for event in graph.astream_events(inputs, version="v2"):
        kind = event["event"]
        
        # 4.1.1 LLM token 输出事件
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            token = chunk.content
            if token:
                yield {"type": "token", "content": token}
        
        # 4.1.2 工具开始执行事件
        elif kind == "on_tool_start":
            tool_name = event["name"]  # 工具名称，如 "get_weather"
            tool_input = event["data"].get("input")  # 工具输入参数
            yield {"type": "tool_start", "tool_name": tool_name, "input": tool_input}
        
        # 4.1.3 工具执行完成事件
        elif kind == "on_tool_end":
            tool_output = event["data"].get("output")  # 工具返回结果
            yield {"type": "tool_end", "output": tool_output}
```

### 4.2 代码讲解

| 位置 | 代码 | 作用 |
|------|------|------|
| 4.1.1 | `on_chat_model_stream` | LLM 每输出一个 token 触发一次，用于实时显示文本 |
| 4.1.2 | `on_tool_start` | 工具开始执行时触发，前端可显示"正在调用 xxx..." |
| 4.1.3 | `on_tool_end` | 工具执行完成后触发，前端可显示工具返回结果 |

**关键理解**：
- 这些事件不是 LLM 发出的，是 LangGraph 框架自动触发的
- 当 LLM 输出 `Action: get_weather` 时，框架自动执行工具并触发事件
- 前端可以根据事件类型显示不同的 UI（token 打字效果 / 工具加载状态 / 工具结果）

### 4.3 事件字段说明（工具调用）

| 事件类型 | 字段 | 示例值 | 含义 |
|----------|------|--------|------|
| `on_tool_start` | `event["name"]` | `"get_weather"` | 工具名称 |
| `on_tool_start` | `event["data"]["input"]` | `{"city": "北京"}` | 工具输入参数 |
| `on_tool_end` | `event["data"]["output"]` | `"北京天气：晴，25°C"` | 工具返回结果 |

### 4.4 FastAPI + SSE 推送示例

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.post("/stream")
async def stream_chat(request: ChatRequest):
    async def event_generator():
        # 遍历所有事件（包括工具调用）
        async for event_data in stream_with_tools(request.message):
            # 序列化为 JSON 发送
            yield f"data: {json.dumps(event_data)}\n\n"
        
        # 结束标记
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
```

### 4.5 SSE 消息格式示例

```
data: {"type": "token", "content": "北京"}
data: {"type": "token", "content": "天气"}
data: {"type": "tool_start", "tool_name": "get_weather", "input": {"city": "北京"}}
data: {"type": "tool_end", "output": "北京天气：晴，25°C"}
data: {"type": "token", "content": "。"}
data: [DONE]
```

---

## 6 FastAPI + SSE 推送到前端（简化版）

**来源**: LangGraph 官方教程
┌─────────────────────────────┐
│      FastAPI 后端            │
│                             │
前端 fetch → POST →   │  stream_chat() 函数         │
│       │                    │
│       ▼                    │
│  graph.astream_events()    │
│       │                    │
│       ▼                    │
│  yield "data: xxx\n\n"    │
│       │                    │
└───────┼─────────────────────┘
        │ SSE 流
        ▼
┌─────────────────────────────┐
│      浏览器 EventSource     │
│  收到 data: xxx\n\n        │
│  解析并显示                 │
└─────────────────────────────┘

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.post("/stream")
async def stream_chat(request: ChatRequest):
    async def event_generator():
        async for token in stream_tokens(request.message):
            # SSE 格式：每行必须以 "data: " 开头，以 "\n\n" 结尾
            yield f"data: {token}\n\n"
        # 通知前端流结束
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲——关键！
        },
    )
```

**关键注意事项**：
- `X-Accel-Buffering: no` 是必须的，否则 Nginx 会缓冲整个响应
- `streaming=True` 必须在 LLM 实例上设置
- `version="v2"` 是 LangGraph 0.2+ 必须的参数
规则：

每行以 data: 开头
以 \n\n 结尾

SSE 格式说明
data: 你      ← 第一个 token
data: 好      ← 第二个 token
data: 啊      ← 第三个 token
data: [DONE]  ← 结束标记
---

## 7 React 前端消费流式数据

**来源**: LangGraph + React 官方教程 2026-01-14

### 7.1 简化版（仅支持 LLM token 流式）

```tsx
// components/StreamingChat.tsx
import { useState } from "react"

export default function StreamingChat() {
  const [output, setOutput] = useState("")      // 7.1.1 存储 LLM 输出的文本
  const [loading, setLoading] = useState(false)  // 7.1.2 控制加载状态

  async function sendMessage(userInput: string) {
    setOutput("")        // 7.1.3 清空上一次的输出
    setLoading(true)     // 7.1.4 开始加载

    // 7.1.5 发送 POST 请求到后端
    const response = await fetch("http://localhost:8000/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userInput }),
    })

    // 7.1.6 获取响应体的读取器（用于消费流式数据）
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()

    // 7.1.7 循环读取流数据
    while (true) {
      const { done, value } = await reader.read()
      if (done) break  // 流结束，退出循环

      // 7.1.8 解码二进制数据为字符串（stream: true 处理跨 chunk 的多字节字符）
      const chunk = decoder.decode(value, { stream: true })

      // 7.1.9 解析每一行 SSE 数据
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          // 7.1.10 移除 "data: " 前缀，获取实际数据
          const token = line.slice(6)
          
          // 7.1.11 检查是否为结束标记
          if (token === "[DONE]") {
            setLoading(false)
            return
          }
          
          // 7.1.12 逐 token 追加到输出（打字机效果）
          setOutput((prev) => prev + token)
        }
      }
    }

    setLoading(false)  // 7.1.13 加载完成
  }

  return (
    <div>
      <button onClick={() => sendMessage("天气怎么样？")} disabled={loading}>
        {loading ? "流式输出中…" : "提问"}
      </button>
      {/* 7.1.14 显示 LLM 输出的内容 */}
      <pre style={{ whiteSpace: "pre-wrap" }}>{output}</pre>
    </div>
  )
}
```
```
**简化版关键点**：
- 7.1.1-7.1.2：状态管理（output 输出内容，loading 加载状态）
- 7.1.5：使用 fetch 发送 POST 请求
- 7.1.6-7.1.7：获取 ReadableStream 读取器，循环读取流数据
- 7.1.9-7.1.12：解析 SSE 格式，移除 "data: " 前缀，逐 token 追加
```

**关键注意事项**：
- `{ stream: true }` 处理跨 chunk 的多字节字符
- 使用 `fetch` + `ReadableStream` 不需要外部库
- SSE 是单向的，如需双向通信需用 WebSocket

### 7.2 完整版（支持 LLM token + Tool Call）

```tsx
// components/StreamingChat.tsx
import { useState } from "react"

// 7.2.1 定义事件类型接口（对应后端发送的 JSON 格式）
interface StreamEvent {
  type: "token" | "tool_start" | "tool_end" | "end"  // 事件类型
  content?: string    // LLM token 内容（type 为 token 时）
  tool_name?: string // 工具名称（type 为 tool_start 时）
  input?: object     // 工具输入参数（type 为 tool_start 时）
  output?: string    // 工具返回结果（type 为 tool_end 时）
}

export default function StreamingChat() {
  const [output, setOutput] = useState("")        // 7.2.2 存储 LLM 输出的文本
  const [toolStatus, setToolStatus] = useState<string>("")  // 7.2.3 存储工具调用状态
  const [loading, setLoading] = useState(false)  // 7.2.4 控制加载状态

  async function sendMessage(userInput: string) {
    setOutput("")        // 7.2.5 清空上一次的 LLM 输出
    setToolStatus("")    // 7.2.6 清空工具状态
    setLoading(true)     // 7.2.7 开始加载

    // 7.2.8 发送 POST 请求到后端（后端需使用 4.4 完整版流式函数）
    const response = await fetch("http://localhost:8000/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userInput }),
    })

    // 7.2.9 获取响应体的读取器
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()

    // 7.2.10 循环读取流数据
    while (true) {
      const { done, value } = await reader.read()
      if (done) break  // 流结束，退出循环

      // 7.2.11 解码二进制数据为字符串
      const chunk = decoder.decode(value, { stream: true })

      // 7.2.12 解析每一行 SSE 数据
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          // 7.2.13 移除 "data: " 前缀，获取实际数据
          const dataStr = line.slice(6)
          
          // 7.2.14 检查是否为结束标记
          if (dataStr === "[DONE]") {
            setLoading(false)
            setToolStatus("")  // 7.2.15 清空工具状态
            return
          }
          
          // 7.2.16 解析 JSON（因为后端发送的是 JSON 格式的 SSE）
          const data: StreamEvent = JSON.parse(dataStr)
          
          // 7.2.17 根据事件类型分别处理
          if (data.type === "token" && data.content) {
            // LLM token - 打字机效果，逐字追加到输出
            setOutput((prev) => prev + data.content)
          } else if (data.type === "tool_start") {
            // 工具开始执行 - 显示工具名称和输入参数
            setToolStatus(`正在调用 ${data.tool_name}，参数：${JSON.stringify(data.input)}`)
          } else if (data.type === "tool_end") {
            // 工具执行完成 - 显示工具返回结果
            setToolStatus(`工具 ${data.tool_name} 返回：${data.output}`)
          }
        }
      }
    }

    setLoading(false)
    setToolStatus("")  // 7.2.18 加载完成，清空工具状态
  }

  return (
    <div>
      <button onClick={() => sendMessage("北京天气怎么样？")} disabled={loading}>
        {loading ? "流式输出中…" : "提问"}
      </button>
      
      {/* 7.2.19 工具调用状态显示 */}
      {toolStatus && <div style={{ color: "#666" }}>{toolStatus}</div>}
      
      {/* 7.2.20 LLM 输出的内容 */}
      <pre style={{ whiteSpace: "pre-wrap" }}>{output}</pre>
    </div>
  )
}
```

### 7.3 代码讲解

| 位置 | 代码 | 作用 |
|------|------|------|
| 7.2.1 | `interface StreamEvent` | 定义事件类型接口，包含 token/tool_start/tool_end 三种类型 |
| 7.2.2 | `setOutput` | 存储 LLM 生成的文本 token |
| 7.2.3 | `setToolStatus` | 存储工具调用状态（工具开始/结束） |
| 7.2.16 | `JSON.parse(dataStr)` | 解析 JSON（因为后端发送的是 JSON 格式） |
| 7.2.17 | `data.type === "token"` | LLM token - 打字机效果 |
| 7.2.17 | `data.type === "tool_start"` | 工具开始执行，显示"正在调用 xxx..." |
| 7.2.17 | `data.type === "tool_end"` | 工具执行完成，显示工具返回结果 |

**完整版与简化版的区别**：

| 对比项 | 7.1 简化版 | 7.2 完整版 |
|--------|-----------|-----------|
| 状态管理 | `output`, `loading` | `output`, `toolStatus`, `loading` |
| 数据格式 | 纯文本 token | JSON 对象 |
| 解析方式 | `line.slice(6)` 直接获取文本 | `JSON.parse()` 解析对象 |
| 工具调用 | ❌ 不支持 | ✅ 支持 tool_start/tool_end |
| 适用后端 | 第6章 简化版 | 4.4 完整版（带工具调用） |

---

**文档结束**

**更新时间**: 2026-04-03 05:39:53
**版本**: v1.1
**更新说明**: 新增第4节"工具调用（Tool Call）事件处理"，包含完整代码、代码讲解、事件字段说明、SSE 格式示例，以及前端处理工具调用事件的代码
