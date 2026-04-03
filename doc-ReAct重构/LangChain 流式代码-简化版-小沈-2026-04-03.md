# LangChain 流式输出代码

**文档版本**: v1.0
**创建时间**: 2026-04-03 04:26:13
**编写人**: 小沈
**存放位置**: D:\OmniAgentAs-desk\doc-react步骤\
**来源**: 从 commit fabd3d16 的 LangChain-ReAct-学习报告-补充 中提取的 16.3 节内容

---

## 1 LangChain 流式输出（Streaming）

### 1.1 Python 端代码
 后端 FastAPI + SSE
**来源**: LangChain 0.2+ 官方示例
后端 FastAPI + SSE
```
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        # 1. 创建 Agent
        agent = create_agent(model="gpt-4", tools=[get_weather])
        
        # 2. 遍历事件
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": request.message}]},
            version="v2"
        ):
            kind = event["event"]
            
            # 3. 根据事件类型发送不同数据
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"].content
                if chunk:
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            elif kind == "on_tool_start":
                tool_name = event["name"]
                tool_input = event["data"].get("input")
                yield f"data: {json.dumps({'type': 'tool_start', 'tool_name': tool_name, 'input': tool_input})}\n\n"
            
            elif kind == "on_tool_end":
                tool_output = event["data"].get("output")
                yield f"data: {json.dumps({'type': 'tool_end', 'output': tool_output})}\n\n"
            
            elif kind == "on_chat_model_end":
                yield "data: {\"type\": \"end\"}\n\n"
        
        # 4. 结束标记
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"}  # 关键：禁用 Nginx 缓冲
    )
```

```python
# LangChain 0.2+ 推荐方式
from langchain.agents import create_agent

agent = create_agent(
    model="gpt-4",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

# 流式输出
async for event in agent.astream_events(
    {"messages": [{"role": "user", "content": "北京天气怎么样？"}]},
    version="v2",
):
    kind = event["event"]
    
    if kind == "on_chat_model_stream":
        # LLM 生成的 chunk
        chunk = event["data"]["chunk"]
        print(f"chunk: {chunk.content}")
        # 可推送 chunk.content 到前端
    
    elif kind == "on_tool_start":
        # 工具开始执行
        tool_name = event["name"]
        tool_input = event["data"].get("input")
        print(f"工具开始: {tool_name}, 输入: {tool_input}")
        # 可推送 "工具 xxx 开始执行" 到前端
    
    elif kind == "on_tool_end":
        # 工具执行结束
        tool_output = event["data"].get("output")
        print(f"工具结果: {tool_output}")
        # 可推送工具结果到前端
    
    elif kind == "on_chat_model_end":
        # LLM 生成结束
        print("LLM 生成结束")
        # 可推送结束标志到前端
```
用户提问："北京天气怎么样？"
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                     Python 后端 (FastAPI)                     │
│                                                               │
│   agent.astream_events()                                      │
│        │                                                      │
│        ▼                                                      │
│   ┌────────────┐    ┌────────────┐    ┌────────────┐          │
│   │ LLM 开始   │ →  │ 工具执行   │ →  │ LLM 结束   │          │
│   │ (stream)   │    │ (tool)     │    │ (end)      │          │
│   └────────────┘    └────────────┘    └────────────┘          │
│        │                  │                  │               │
│        ▼                  ▼                  ▼               │
│   yield chunk         yield tool         yield end            │
│        │                  │                  │               │
└────────┼──────────────────┼──────────────────┼───────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
   ┌─────────────────────────────────────────────────────────┐
   │                 SSE (Server-Sent Events)                 │
   │   data: {"type": "chunk", "content": "北京"}            │
   │   data: {"type": "chunk", "content": "天气"}            │
   │   data: {"type": "tool_start", "tool_name": "search"}  │
   │   data: {"type": "tool_end", "output": "晴，25°C"}      │
   │   data: {"type": "end"}                                  │
   └─────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│                      前端浏览器                               │
│                                                               │
│   EventSource 监听                                            │
│        │                                                      │
│        ▼                                                      │
│   ┌──────────────────────────────────────────────────────┐  │
│   │ onmessage 回调                                          │  │
│   │   ├── case 'chunk': appendToChat() → 逐字显示          │  │
│   │   ├── case 'tool_start': showToolStatus() → 显示加载  │  │
│   │   ├── case 'tool_end': showToolResult() → 显示结果    │  │
│   │   └── case 'end': eventSource.close() → 结束          │  │
│   └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```
{"messages": [
    {"role": "user", "content": "用户问题"},
    {"role": "assistant", "content": "历史回答"},  # 可选
    {"role": "system", "content": "系统提示"}      # 可选
]}
```
事件对象完整结构
# on_chat_model_stream 事件的完整结构
{
    "event": "on_chat_model_stream",
    "run_id": "abc123-uuid",
    "parent_ids": [],
    "name": "agent",  # 节点名称
    "tags": ["llm"],
    "metadata": {},
    "data": {
        "chunk": AIMessageChunk(
            content="北京天气",  # 实际的 token 文本
            additional_kwargs={},
            usage_metadata={"input_tokens": 10, "output_tokens": 5}
        )
    }
}

# on_tool_start 事件的完整结构
{
    "event": "on_tool_start",
    "run_id": "abc123-uuid",
    "name": "get_weather",  # 工具名称
    "data": {
        "input": {"city": "北京"}  # 工具输入参数
    }
}

# on_tool_end 事件的完整结构
{
    "event": "on_tool_end",
    "run_id": "abc123-uuid",
    "name": "get_weather",
    "data": {
        "output": "北京天气：晴，25°C"  # 工具返回结果
    }
}

### 1.2 前端 SSE 消费代码

**来源**: JavaScript 前端示例
SSE 消息格式 服务器发送的消息格式：
```
data: {"type": "chunk", "content": "北京"}

data: {"type": "tool_start", "tool_name": "get_weather"}

data: {"type": "end"}
```
```javascript
// 前端使用 EventSource 消费 SSE 流
// EventSource 是浏览器原生 API，用于：

// 接收服务器推送的单向消息
// 自动维护连接、自动重连
// 比 WebSocket 更轻量
//  前端处理逻辑
const eventSource = new EventSource('/api/chat/stream');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'chunk':
      // 处理 LLM 生成的文本块
      appendToChat(data.content);
      break;
    case 'tool_start':
      // 工具开始执行
      showToolStatus(data.tool_name, 'running');
      break;
    case 'tool_end':
      // 工具执行结束
      showToolResult(data.tool_name, data.output);
      break;
    case 'end':
      // 流结束
      eventSource.close();
      break;
  }
};

// 连接出错时触发
eventSource.onerror = (error) => {
    console.error('SSE 连接错误:', error);
    eventSource.close();  // 关闭连接
};

// 连接成功时触发
eventSource.onopen = () => {
    console.log('SSE 连接已建立');
};
```

3.4 appendToChat 函数示例
```
function appendToChat(content) {
    // 获取聊天容器
    const chatContainer = document.getElementById('chat-container');
    
    // 追加新内容（实现打字机效果）
    chatContainer.textContent += content;
    
    // 自动滚动到底部
    chatContainer.scrollTop = chatContainer.scrollHeight;
}
```
前端完整实现
```
async function sendMessage(message) {
    const chatContainer = document.getElementById('chat-container');
    
    // 发送请求
    const response = await fetch('/chat/stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message})
    });
    
    // 获取流读取器
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        
        // 解码 chunk
        const chunk = decoder.decode(value, {stream: true});
        
        // 解析每行 SSE 数据
        for (const line of chunk.split('\n')) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                
                // 处理不同类型
                if (data.type === 'chunk') {
                    chatContainer.textContent += data.content;
                } else if (data.type === 'tool_start') {
                    showStatus(`正在调用 ${data.tool_name}...`);
                } else if (data.type === 'tool_end') {
                    showResult(data.output);
                } else if (data.type === 'end') {
                    showStatus('回答完成');
                }
            }
        }
    }
}
```
### 1.3 关键说明

| 要点 | 说明 |
|------|------|
| `version="v2"` | LangGraph 0.2+ 必须的参数 |
| `on_chat_model_stream` | LLM token 级事件 |
| `on_tool_start` | 工具开始执行事件 |
| `on_tool_end` | 工具执行结束事件 |
| `on_chat_model_end` | LLM 生成完成事件 |

---

## 2 事件类型与字段

| 事件类型 | 字段 | 含义 |
|----------|------|------|
| `on_chat_model_stream` | `event["data"]["chunk"].content` | LLM 生成的 token |
| `on_tool_start` | `event["name"]`, `event["data"]["input"]` | 工具名称和输入 |
| `on_tool_end` | `event["data"]["output"]` | 工具执行结果 |
| `on_chat_model_end` | 无 | LLM 生成完成 |

---

**文档结束**

**更新时间**: 2026-04-03 04:26:13
**版本**: v1.0
 LangGraph 的工作方式
 用户输入
     │
     ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                    LangGraph Agent                          │
 │                                                              │
 │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐   │
 │  │  LLM    │ →  │ Tool    │ →  │  LLM    │ →  │  LLM    │   │
 │  │ (节点1) │    │ (节点2)  │    │ (节点3) │    │ (节点4) │   │
 │  └─────────┘    └─────────┘    └─────────┘    └─────────┘   │
 │       │              │              │              │        │
 │       ▼              ▼              ▼              ▼        │
 │  ┌──────────────────────────────────────────────────────┐   │
 │  │              事件系统 (Event Emitter)                  │   │
 │  │   当节点开始/结束/输出时，自动触发相应事件             │   │
 │  └──────────────────────────────────────────────────────┘   │
 │                           │                                  │
 └───────────────────────────┼──────────────────────────────────┘
                             ▼
                     astream_events 捕获

关键理解：

LangGraph 把 Agent 拆成多个节点（Node）
每个节点执行时会触发事件（Event）
astream_events 只是一个事件监听器
事件触发机制详解
2.1 节点执行时自动触发事件
当 LangGraph 执行时，会自动触发这些事件：

时间线
时间线
────────────────────────────────────────────────────────────→

节点1: LLM
│  开始 → on_chat_model_start
│  输出token → on_chat_model_stream (每输出一个token触发一次)
│  结束 → on_chat_model_end
│
节点2: Tool (get_weather)
│  开始 → on_tool_start
│  执行 → ...
│  结束 → on_tool_end
│
节点3: LLM (再次调用)
│  开始 → on_chat_model_start
│  ...
│  结束 → on_chat_model_end

这些事件不是 LLM 发出的，是框架自动发的

# 不是 LLM 告诉框架 "我要输出 token 了"
# 而是框架在 LLM 输出时自动捕获并触发事件

# 伪代码大致逻辑：
class ChatModel:
    async def ainvoke(self, input):
        # LLM 开始调用
        on_chat_model_start.fire()
        
        # LLM 输出（流式）
        async for token in self._stream():
            on_chat_model_stream.fire(chunk=token)  # 每有一个 token 就触发一次
            yield token
        
        # LLM 调用结束
        on_chat_model_end.fire()

class Tool:
    async def arun(self, input):
        on_tool_start.fire(input=input)  # 工具开始
        result = self._execute(input)
        on_tool_end.fire(output=result)   # 工具结束

astream_events 内部实现
3.1 它本质是一个"事件过滤器"
# astream_events 内部大致逻辑（简化版）
async def astream_events(self, input, version="v2"):
    # 1. 创建事件发射器
    event_emitter = EventEmitter()
    
    # 2. 把事件发射器注入到图的每个节点
    for node in self.graph.nodes:
        node.bind_event_emitter(event_emitter)
    
    # 3. 订阅感兴趣的事件
    subscribed_events = ["on_chat_model_stream", "on_tool_start", "on_tool_end", ...]
    
    # 4. 执行图
    async for step in self.graph.astream(input):
        # 5. 每当有事件触发，就 yield 出去
        for event in event_emitter.get_events():
            if event.type in subscribed_events:
                yield event

3.2 事件来源分类
事件类型	谁触发	触发时机
on_chat_model_stream	LLM 节点	LLM 每次输出一个 token
on_chat_model_start	LLM 节点	LLM 开始调用
on_chat_model_end	LLM 节点	LLM 调用结束
on_tool_start	Tool 节点	工具开始执行
on_tool_end	Tool 节点	工具执行完成
on_chain_start	任何节点	节点开始
on_chain_end	任何节点	节点结束

✅ 正确理解：
LLM 输出 "Action: get_weather" → LangGraph 解析出要调用工具 
    → 框架自动执行工具 → 自动触发 on_tool_start
    
    实际流程
    1. LLM 输出: "Thought: 我要查天气\nAction: get_weather\nAction Input: {\"city\": \"北京\"}"
                        │
                        ▼
    2. LangGraph OutputParser 解析
                       │
                       ▼
    3. 识别出要调用 get_weather 工具
                       │
                       ▼
    4. LangGraph 内部执行: await get_weather.arun({"city": "北京"})
                       │
                       ▼
    5. 工具执行前 → 框架自动触发 on_tool_start 事件
       工具执行后 → 框架自动触发 on_tool_end 事件

LangGraph 标准库
1. 安装
pip install langgraph
2. 核心 API 概览
模块	用途	关键类/函数
langgraph.graph	图结构	StateGraph, MessageGraph, END, START
langgraph.pregel	执行引擎	Pregel（图的运行器）
langgraph.checkpoints	状态保存	MemorySaver, PostgresSaver
langgraph.constants	常量	INPUT, INTERRUPT, RESPONSE
langgraph.types	类型定义	Command, RetryPolicy
核心 API 示例
1. 创建 Agent 图
from langgraph.graph import StateGraph, END, START
from langgraph.pregel import Pregel
from typing import TypedDict

# 1. 定义状态
class AgentState(TypedDict):
    messages: list
    step_count: int

# 2. 创建图
builder = StateGraph(AgentState)

# 3. 添加节点（函数）
def think_node(state):
    return {"messages": [...], "step_count": state["step_count"] + 1}

def act_node(state):
    return {"messages": [...]}

# 4. 注册节点
builder.add_node("think", think_node)
builder.add_node("act", act_node)

# 5. 设置边
builder.add_edge(START, "think")
builder.add_edge("think", "act")
builder.add_edge("act", END)

# 6. 编译
agent = builder.compile()

2. 流式输出
# 使用 astream_events
async for event in agent.astream_events(
    {"messages": [{"role": "user", "content": "你好"}]},
    version="v2"
):
    print(event)

3. Checkpoint（断点续跑）
from langgraph.checkpoints.memory import MemorySaver

# 创建检查点存储
checkpointer = MemorySaver()

# 编译时传入
agent = builder.compile(checkpointer=checkpointer)

# 暂停后恢复
config = {"configurable": {"thread_id": "123"}}
result = agent.invoke(input, config=config)
官方文档
