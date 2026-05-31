# Agent与LLM的模式关系分析

**创建时间**: 2026-05-30 12:41:51  
**编写人**: 小沈  
**版本**: v1.0  
**关联问题**: 2.22+2.29 重试机制收敛（从重试视角分析Agent与LLM的4种交互模式）

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-05-30 12:41:51 | 小沈 | 初始版本，从重试视角分析Agent与LLM的4种交互模式 |
| v1.1 | 2026-05-30 12:55:55 | 小沈 | 修正内部标题与文件名一致 |
| **v1.2** | **2026-05-30 13:10:00** | **小沈** | **重构全文：从"重试机制分析"改为"Agent与LLM的模式关系分析"，新增决策流，原重试内容降级为附录** |

---

## 一、Agent与LLM的4种交互模式概述

### 1.1 4种交互模式总览

| 模式 | 函数 | 所属层 | 功能 | 典型场景 |
|------|------|--------|------|---------|
| **模式1：非流式交互** | `BaseAIService.chat()` | LLM服务层 | 发送完整请求，等待完整响应 | 简单问答、工具结果验证 |
| **模式2：流式交互** | `BaseAIService.stream()` | LLM服务层 | 发送请求，逐块接收响应 | 实时对话、打字机效果 |
| **模式3：SSE流式处理** | `chat_stream_query()` | 聊天流层 | 处理流式SSE事件，构建消息 | 前端展示Agent执行过程 |
| **模式4：ReAct循环** | `BaseAgent.run()` | Agent层 | 思考→行动→观察循环 | 复杂任务执行、多步推理 |

### 1.2 架构分层

```
┌─────────────────────────────────────────┐
│              聊天流层（chat_stream）       │
│  chat_stream_query()                     │
│  职责：处理SSE事件，构建消息              │
├─────────────────────────────────────────┤
│              Agent层（BaseAgent）         │
│  BaseAgent.run()                         │
│  职责：ReAct循环编排，工具调度            │
├─────────────────────────────────────────┤
│             LLM服务层（BaseAIService）    │
│  chat()  /  stream()                     │
│  职责：LLM调用封装，响应解析             │
└─────────────────────────────────────────┘
```

---

## 二、4种模式的详细分析

### 2.1 模式1：非流式交互（BaseAIService.chat()）

**路径**：`BaseAIService.chat()` → `_post_with_retry()` → LLM API

**特点**：
- 同步等待完整响应
- 适合不需要实时反馈的场景
- 重试由 `_post_with_retry` → `RetryEngine` 处理

**代码路径**：`core.py` → 发送请求 → 等待完整响应 → 返回

### 2.2 模式2：流式交互（BaseAIService.stream()）

**路径**：`BaseAIService.stream()` → `_StreamRetryContext` → LLM API

**特点**：
- 异步逐块接收响应（打字机效果）
- 适合实时对话场景
- 重试由 `_StreamRetryContext` → `RetryEngine.execute_async_context()` 处理

**代码路径**：`core.py` → 建立流式连接 → 逐块yield响应 → 关闭连接

### 2.3 模式3：SSE流式处理（chat_stream_query()）

**路径**：`chat_stream_query()` → `BaseAIService.stream()` → LLM API

**特点**：
- 在流式交互之上封装SSE事件处理
- 构建消息结构，供前端消费
- 重试由 `RetryCounter`（纯计数器）处理

**代码路径**：`chat_stream_query.py` → 调用stream()获取流 → 构建SSE事件yield → 异常时重试

### 2.4 模式4：ReAct循环（BaseAgent.run()）

**路径**：`BaseAgent.run()` → 循环：思考→执行工具→观察→继续/退出

**特点**：
- 多步推理、工具调用的核心循环
- 支持并行工具、回滚、chunk流式输出
- 重试由 `RetryEngine`（空响应重试）处理

**代码路径**：`base_react.py` → parse → execute tool → observe → loop/exit

---

## 三、4种模式的关系

### 3.1 4种模式分别是什么？

| 模式 | 函数 | 所属层 | 功能 | 说明 |
|------|------|--------|------|------|
| **模式1：非流式交互** | `BaseAIService.chat()` | LLM服务层 | 非流式调用 | 发送完整请求，等待完整响应 |
| **模式2：流式交互** | `BaseAIService.stream()` | LLM服务层 | 流式调用 | 发送请求，逐块接收响应 |
| **模式3：SSE流式处理** | `chat_stream_query()` | 聊天流层 | 流式SSE主循环 | 处理流式SSE事件 |
| **模式4：ReAct循环** | `BaseAgent.run()` | Agent层 | ReAct循环 | Agent执行任务的主循环 |

### 3.2 4种模式的关系

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent层（BaseAgent）                      │
│                                                             │
│  BaseAgent.run()  ←── ReAct循环                             │
│       │                                                     │
│       └── 调用LLM获取响应                                    │
│              │                                              │
│              ▼                                              │
├─────────────────────────────────────────────────────────────┤
│                    LLM服务层（BaseAIService）                │
│                                                             │
│  ├── chat()      ←── 非流式交互（返回完整响应）              │
│  │                                                              │
│  └── stream()    ←── 流式交互（返回流式响应）                │
│         │                                                    │
│         └── 流式数据                                         │
│                │                                            │
│                ▼                                            │
├─────────────────────────────────────────────────────────────┤
│                    聊天流层（chat_stream_query）              │
│                                                             │
│  chat_stream_query()  ←── SSE流式处理                       │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 4种模式是4个分支还是4个阶段？

**答案：是4个不同的使用场景/分支，不是流程的4个阶段。**

| 模式 | 函数 | 说明 |
|------|------|------|
| **模式1：非流式交互** | `BaseAIService.chat()` | 用户发送消息，等待完整响应 |
| **模式2：流式交互** | `BaseAIService.stream()` | 用户发送消息，逐块接收响应 |
| **模式3：SSE流式处理** | `chat_stream_query()` | 处理流式SSE事件 |
| **模式4：ReAct循环** | `BaseAgent.run()` | Agent执行任务的主循环 |

### 3.4 4种模式的调用关系图

```
用户发送消息
    │
    ├── 模式1：非流式交互
    │       └── BaseAIService.chat()
    │
    ├── 模式2：流式交互
    │       └── BaseAIService.stream()
    │
    ├── 模式3：SSE流式处理
    │       └── chat_stream_query()
    │               └── 内部调用 BaseAIService.stream()
    │
    └── 模式4：ReAct循环
            └── BaseAgent.run()
                    └── 内部调用 BaseAIService.chat() 获取LLM响应
```

### 3.5 4种模式的区别

| 维度 | chat() | stream() | chat_stream_query() | BaseAgent.run() |
|------|--------|----------|---------------------|-----------------|
| **所属层** | LLM服务层 | LLM服务层 | 聊天流层 | Agent层 |
| **调用方式** | 同步等待 | 异步流式 | 异步流式 | 异步循环 |
| **响应类型** | 完整响应 | 流式响应 | SSE事件 | Agent执行结果 |
| **典型场景** | 简单问答 | 实时对话 | 流式展示 | 任务执行 |

---

## 四、模式选择决策流

```
用户请求
    │
    ├── 是否走Agent流程？
    │   ├── 是 → 模式4：BaseAgent.run()
    │   │         └── ReAct循环中调用LLM → 模式1：chat()
    │   │
    │   └── 否 → 是否需要流式？
    │           ├── 是 → 模式3：chat_stream_query()
    │           │         └── 内部调用 → 模式2：stream()
    │           │
    │           └── 否 → 模式1：chat()
    │
    ▼
返回结果
```

**决策点**：
1. **是否走Agent** → 由`intent_classifier`判断（复杂任务走Agent，简单问答直接chat）
2. **是否流式** → 由前端请求参数决定（`stream=true/false`）
3. **chat_stream_query vs stream** → `chat_stream_query`是`stream`的上层封装，加了一层SSE事件构建

---

## 五、附：从重试视角看这4种模式

> 本节是对[重试机制详细分析]文档核心内容的摘要，仅保留与模式关系相关的重试信息。

### 5.1 各模式的重试机制

| 模式 | 重试机制 | 文件 | 触发条件 |
|------|---------|------|---------|
| **模式1：chat()** | `_post_with_retry` → RetryEngine | `core.py:158` | 429异常 |
| **模式2：stream()** | `_StreamRetryContext` → RetryEngine.execute_async_context() | `core.py:57` | 429状态码 |
| **模式3：chat_stream_query()** | RetryCounter（纯计数器） | `chat_stream_query.py:209` | idle_timeout/network_error |
| **模式4：BaseAgent.run()** | RetryEngine（空响应重试） | `base_react.py` | parse_error/empty_response |

### 5.2 重试与模式的关系

- **4种模式 = 4个不同的重试场景**，不是流程的4个阶段
- 每种模式有自己独立的触发条件和重试策略
- 只有模式2（stream）做了优化：`_StreamRetryContext` 从手写重试循环改为委托 `RetryEngine.execute_async_context()`

---

**文档完成时间**: 2026-05-30 12:41:51  
**编写人**: 小沈  
**版本**: v1.0
