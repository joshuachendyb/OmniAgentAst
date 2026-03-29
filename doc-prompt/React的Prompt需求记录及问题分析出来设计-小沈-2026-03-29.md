# React的Prompt需求记录及问题分析出来设计

**创建时间**: 2026-03-29 05:08:14 **版本**: v2.4 **编写人**: 小沈 **更新时间**: 2026-03-29 11:19:45

---

## 一、需求（为什么记录Prompt）

### 1.1 核心目的

**记录Prompt不是为了记录而记录，而是为了发现代码问题！**

通过记录 Prompt 的完整组装过程和 LLM 调用信息，可以发现：
- ReAct Loop 的运行机制是否正确
- 发送给 LLM 的 messages 是否正确、完整
- LLM 返回结果的处理是否正确
- 前端 UI 显示异常的根本原因

### 1.2 具体需求

| 需求编号 | 需求描述 | 状态 |
|---------|---------|------|
| 需求1 | 每个对话生成一个独立的JSON文件 | ✅ 满足 |
| 需求2 | 每次调用LLM时追加Prompt历史到文件 | ❌ 需要修复 |
| 需求3 | 分析prompt在"thought"阶段是如何生成和组装的 | ✅ 设计完成 |
| 需求4 | 从第一个thought开始记录prompt的变化过程 | ✅ 设计完成 |

---

## 二、发现的问题

### 2.1 问题汇总表

| 问题编号 | 问题描述 | 严重程度 | 优先级 | 验证结果 |
|---------|---------|---------|--------|---------|
| **P1** | conversation_history 重复添加 assistant（strategy内部+base_react.py:244） | **严重** | P0 | ✅ 确认：小强发现，修正原分析 |
| **P2** | SSE 事件结构不一致：observation 事件使用 obs_ 前缀 | 中等 | P1 | ✅ 确认 |
| **P3** | start_request() 被重复调用，数据被覆盖 | 中等 | P1 | ✅ 确认 |
| **P4** | save() 从未被调用，JSON 文件不生成 | 中等 | P1 | ✅ 确认 |
| **P5** | _on_after_loop() 未被调用 | 低 | P2 | ✅ 确认 |
| **P6** | llm_client 没有 chat_with_tools/chat_with_response_format 方法 | **严重** | P0 | ✅ 确认 |
| **P7** | 策略选择和实际执行不匹配 | **严重** | P0 | ✅ 确认 |
| **P8** | TextStrategy 返回纯文本，但 parser 期望 JSON | **严重** | P0 | ✅ 确认 |
| **P9** | 循环条件判断顺序错误：先调用LLM再判断是否finish | - | - | ❌ 已排除：代码逻辑正确 |
| **P10** | SSE事件type命名混乱 | 低 | P2 | ⚠️ 部分合理：action_tool应改为action |
| **P11** | 错误处理导致LLM的content被丢弃 | 中等 | P1 | ✅ 确认 |
| **P12** | 历史消息裁剪_trim_history被注释，对话历史无限增长 | **严重** | P0 | ✅ 确认 |
| **P13** | 重复添加 assistant 到 conversation_history（strategy内部 + base_react.py:244） | 中等 | P1 | ✅ 确认：小强发现 |
| **P14** | parsed_obs.content（第2次LLM响应）从未保存到conversation_history | **严重** | P0 | ✅ 确认：小健发现 |
| **P15** | 缺少 Action Input 字段 | - | - | ❌ 已排除：有 tool_params 字段对应 |
| **P16** | parse错误后 continue 导致 SSE 事件不完整（但history正确） | 中等 | P1 | ✅ 确认：小健发现 |

### 2.2 问题优先级

| 优先级 | 问题 | 说明 |
|-------|------|------|
| **P0-紧急** | P1, P6, P7, P8, P12, P14 | 会导致 LLM 调用失败或返回异常结果，前端显示异常（P14为小健发现） |
| P1-高 | P2, P3, P4, P11, P13, P16 | 影响日志记录和调试 |
| P2-低 | P5, P10 | 不影响核心功能（风格问题） |
| **已排除** | P9, P15 | 代码逻辑正确/已有对应字段 |

---

## 三、Prompt记录策略和方法

### 3.1 文件命名规则

```
prompt_{message_id}+{YYYYMMDD_HHMMSS}.json

示例：prompt_msg_abc123+20260329_123045.json
```

### 3.2 文件开头基本信息

| 字段 | 说明 |
|------|------|
| 时间戳 | 文件创建时间 |
| 会话ID | session_id |
| 用户消息ID | user_message_id |
| AI消息ID | AI消息ID |
| 用户消息 | message_id: 用户消息内容 |
| 模型 | 模型名称（如 gpt-4） |
| 提供商 | 提供商（如 openai） |
| 日志文件 | 日志文件路径 |

### 3.3 LLM调用记录结构

每次 LLM 调用记录一次，包含：

| 字段 | 说明 |
|------|------|
| 轮次 | 第几次 LLM 调用 |
| 阶段 | thought / observation（标识是 Loop 的哪个阶段） |
| 组装步骤 | 发送给 LLM 的 messages 逐步累积过程 |
| 最终Prompt | 发送给 LLM 的完整 messages |
| LLM返回 | LLM 返回的 content、action_tool、params |
| 工具执行 | 工具名称、参数、执行结果 |
| 调用耗时 | 毫秒 |

### 3.4 JSON 文件示例

```json
{
  "基本信息": {
    "时间戳": "2026-03-29 12:00:00",
    "会话ID": "abc123",
    "用户消息": "msg_abc123: 帮我整理桌面文件",
    "模型": "gpt-4",
    "提供商": "openai"
  },
  "LLM调用记录": [
    {
      "轮次": 1,
      "阶段": "thought",
      "组装步骤": [
        {"步骤": 1, "操作": "添加 system", "role": "system", "content": "你是一个文件操作助手..."},
        {"步骤": 2, "操作": "添加 user", "role": "user", "content": "帮我整理桌面文件"}
      ],
      "最终Prompt": [
        {"role": "system", "content": "你是一个文件操作助手..."},
        {"role": "user", "content": "帮我整理桌面文件"}
      ],
      "LLM返回": {
        "content": "我需要先查看桌面上有哪些文件",
        "action_tool": "list_directory",
        "params": {"path": "C:\\Users\\Desktop"}
      },
      "工具执行": {
        "工具名称": "list_directory",
        "参数": {"path": "C:\\Users\\Desktop"},
        "执行结果": "success",
        "返回数据": ["文档", "图片", "下载"]
      },
      "调用耗时(ms)": 1250
    },
    {
      "轮次": 2,
      "阶段": "observation",
      "组装步骤": [
        {"步骤": 1, "操作": "添加 system", "role": "system", "content": "..."},
        {"步骤": 2, "操作": "添加 user", "role": "user", "content": "帮我整理桌面文件"},
        {"步骤": 3, "操作": "添加 assistant (第1轮)", "role": "assistant", "content": "我需要先查看..."},
        {"步骤": 4, "操作": "添加 user (第1轮observation)", "role": "user", "content": "Observation: success - ..."}
      ],
      "最终Prompt": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "帮我整理桌面文件"},
        {"role": "assistant", "content": "我需要先查看..."},
        {"role": "user", "content": "Observation: success - ['文档', '图片', '下载']"}
      ],
      "LLM返回": {
        "content": "现在我看到桌面上有3个文件夹",
        "action_tool": "create_directory",
        "params": {"path": "C:\\Users\\Desktop\\分类"}
      },
      "工具执行": {
        "工具名称": "create_directory",
        "参数": {"path": "C:\\Users\\Desktop\\分类"},
        "执行结果": "success"
      },
      "调用耗时(ms)": 980
    }
  ]
}
```

### 3.5 设计实现要点

| 设计点 | 实现方式 |
|--------|---------|
| 独立日志 | 线程局部存储 `_local = threading.local()`，每个请求独立 |
| 数据结构 | start_request() 创建 JSON 结构：`{基本信息, Prompt组装过程, LLM调用记录}` |
| 追加记录 | log_xxx() 从 `_local.current_log` 获取并追加 |
| **实时持久化** | **每次 log_llm_call() 后立即 save()** |
| 最终持久化 | 循环结束时再次 save()（确保完整） |

---

## 四、现有代码的 ReAct Loop 的问题和解决办法

### 4.1 ReAct Loop 机制说明

#### 4.1.1 ReAct 的真正含义

| 术语 | 真正含义 | 谁产生的 |
|------|---------|---------|
| **Thought** | LLM 思考"我应该调用XX工具" | LLM 生成的 |
| **Action** | 实际执行工具 | 程序自动执行的 |
| **Observation** | 工具执行的结果 | 程序自动注入的 |

#### 4.1.2 messages 列表中的 role 含义

```
messages 列表中的 role 含义：

[system]           ← 真正的系统提示（程序员写的）
[user]             ← 真正的用户问题（用户输入的）
[assistant]        ← LLM 说的话（LLM 生成的）
[user(Observation)] ← Agent 自动注入的信息（程序自动添加的，不是用户！）
```

**注意**：`user(Observation)` 中的 "user" 只是 ReAct 框架定义的角色名称，**不是真正的用户**！它是 Agent（程序）自动添加的"工具执行结果"，目的是让 LLM 看到这个结果后继续推理。

#### 4.1.3 messages 列表组装规则

| 规则 | 说明 |
|------|------|
| 固定 | system 消息始终在第1位 |
| 固定 | user 消息始终在第2位 |
| 累积 | 每次循环增加2条：assistant(thought) + user(observation) |

#### 4.1.4 messages 变化过程

```
第1次LLM调用: messages = [system, user]                    → 2条
第2次LLM调用: messages = [system, user, assistant, user]    → 4条
第3次LLM调用: messages = [system, user, assistant, user, assistant, user] → 6条
...
```

### 4.2 问题详解

#### 4.2.1 P1: conversation_history 顺序错误（严重）

**问题描述**

在 `base_react.py:run_stream()` 中：

```python
# 第141-142行：初始化
self.conversation_history = [system, user]  # 2条

# 第152行：第1次 LLM 调用
response = await self._get_llm_response()

# 第213行：添加 Observation（此时还没有 assistant！）
self._add_observation_to_history(observation_text)
# 现在: [system, user, user(Observation)]  ← 3条，缺少 assistant(Thought)！

# 第217行：第2次 LLM 调用 ← 问题在这里！
llm_response = await self._get_llm_response()
# 此时 messages = [system, user, user(Observation)]
# 缺少 assistant(Thought)！

# 第244行：添加 assistant(Thought) ← 太晚了！第2次调用已经结束
self.conversation_history.append({"role": "assistant", "content": thought_content})
```

**问题的后果**

第2次 LLM 调用时，发送给 LLM 的 messages 是：

```
期望: [system, user, assistant(Thought), user(Observation)]
实际: [system, user, user(Observation)]
```

**LLM 看不到自己之前的思考！**

这会导致：
1. LLM 不知道自己之前说了什么
2. LLM 看到的对话不连贯
3. 可能输出矛盾或重复的内容
4. 前端 UI 显示可能出现奇怪的行为

**解决方案**

调整添加顺序：先添加 assistant，后添加 Observation：

```python
# 先添加 assistant(Thought)
self.conversation_history.append({"role": "assistant", "content": thought_content})

# 后添加 user(Observation)
self._add_observation_to_history(observation_text)
```

#### 4.2.2 P2: SSE 事件结构不一致（中等）

**问题描述**

```python
# Thought 事件 (第169-177行)
yield {
    "type": "thought",
    "action_tool": action_tool,      # 直接字段名
    "params": params                 # 直接字段名
}

# Observation 事件 (第229-241行)
yield {
    "type": "observation",
    "obs_action_tool": ...,          # 加了 obs_ 前缀！
    "obs_params": {...}              # 加了 obs_ 前缀！
}
```

**解决方案**

统一字段命名，去掉前缀：

```python
# Observation 事件
yield {
    "type": "observation",
    "action_tool": parsed_obs.get("action_tool"),  # 去掉 obs_ 前缀
    "params": parsed_obs.get("params")              # 去掉 obs_ 前缀
}
```

#### 4.2.3 P3: start_request() 被重复调用（中等）

**问题描述**

| 文件 | 方法 | 状态 |
|------|------|------|
| react_sse_wrapper.py | start_request() | ✅ 创建日志，但被覆盖 |
| file_react.py | start_request() | ❌ 覆盖上面数据 |

**解决方案**

删除 file_react.py:_on_before_loop() 中的 start_request() 调用。

#### 4.2.4 P4: save() 从未被调用（中等）

**问题描述**

save() 从未被调用，导致 JSON 文件没有生成。

**解决方案**

每次 log_llm_call() 后立即调用 save()。

#### 4.2.5 P5: _on_after_loop() 未被调用（低）

**问题描述**

base_react.py:run_stream() 循环结束后没有调用 _on_after_loop()。

**解决方案**

添加 finally 块调用 _on_after_loop()。

#### 4.2.6 P6: llm_client 没有必要的方法（严重）

**问题位置**：`react_sse_wrapper.py` 第349-351行

```python
async def llm_client(message, history=None):
    response = await ai_service.chat(message, history)
    return type('obj', (object,), {'content': response.content})()
```

**问题**：`llm_client` 只有 `message` 和 `history` 两个参数，**没有**：
- `chat_with_tools()` 方法
- `chat_with_response_format()` 方法

**后果**：
- `ToolsStrategy` 检测到没有 `chat_with_tools` 方法，回退到 TextStrategy
- `ResponseFormatStrategy` 调用 `chat_with_response_format()` 时会失败

#### 4.2.7 P7: 策略选择和实际执行不匹配（严重）

| 策略选择 | 期望方法 | 实际执行结果 |
|---------|---------|-------------|
| `tools` | llm_client.chat_with_tools() | ❌ 没有这个方法，回退到 TextStrategy |
| `response_format` | llm_client.chat_with_response_format() | ❌ 会报错：AttributeError |
| `prompt` | TextStrategy | ✅ 正常 |

**关键问题**：即使 LLM 支持 tools 或 response_format，实际执行时也会失败！

#### 4.2.8 P8: TextStrategy 返回纯文本，但 parser 期望 JSON（严重）

**TextStrategy 返回**（第91行）：
```python
return content  # ← 返回纯文本
```

**parser.parse_response() 期望**（tool_parser.py）：
```python
# 期望返回 JSON 格式：
{"content": "...", "action_tool": "...", "params": {...}}
```

**后果**：
- TextStrategy 返回：`"我需要调用 list_directory 工具来查看文件"`
- parser 解析 JSON 失败
- 回退到 `_extract_from_text()` 提取
- 可能提取不到 action_tool，默认返回 `"finish"`
- **LLM 返回的完整 content 被丢弃！**

#### 4.2.9 P14: parsed_obs.content（第2次LLM响应）从未保存到conversation_history（严重）

**问题描述**

在 `base_react.py:run_stream()` 中：

```python
# 第220行：解析第2次LLM响应
parsed_obs = self.parser.parse_response(llm_response)
# parsed_obs 包含：{"content": "第2次LLM的思考", "action_tool": "...", "params": {...}}

# 第244行：添加到历史记录
self.conversation_history.append({"role": "assistant", "content": thought_content})
# ❌ 错误：只保存了第1次LLM的响应（thought_content）
# ❌ 错误：没有保存第2次LLM的响应（parsed_obs.get("content")）
```

**问题的后果**

第2次LLM调用后，conversation_history的变化过程：

```
第2次LLM调用前:
  conversation_history = [system, user, user(Observation)]     ← 缺少assistant(Thought)!

第2次LLM调用后（第217行）:
  第2次LLM返回的响应 → parsed_obs.content = "第2次LLM的思考内容"

第244行（添加assistant）:
  conversation_history.append({"role": "assistant", "content": thought_content})
  结果: [system, user, user(Obs), assistant(第1次的thought)]  ← 保存错了！

第3次LLM调用前:
  conversation_history = [system, user, user(Obs), assistant(第1次)]
  ❌ 缺少第2次LLM的响应！

第3次LLM调用:
  LLM看不到第2次自己说了什么！
  只能看到第1次的thought！
```

**正确的逻辑应该是**

```python
# 第244行：应该保存本次循环中第2次LLM的响应
self.conversation_history.append({"role": "assistant", "content": parsed_obs.get("content", "")})

# 而不是：
self.conversation_history.append({"role": "assistant", "content": thought_content})  # 保存的是第1次的！
```

**问题影响**

1. ReAct 循环无法正确实现
2. LLM 看不到完整的对话历史
3. 第N次调用时，缺少第N-1次的响应
4. 可能导致 LLM 输出重复或矛盾的内容
5. 前端显示可能出现异常

**解决方案**

调整第244行的代码，保存正确的响应内容：

```python
# 保存本次循环中第2次LLM的响应（而不是第1次的）
self.conversation_history.append({"role": "assistant", "content": parsed_obs.get("content", "")})
```

### 4.3 问题流程图

```
LLM 能力探测 → 选择 "tools" 或 "response_format" 策略
                         ↓
          file_react.py:_get_llm_response()
                         ↓
          调用 ToolsStrategy.call() 或 ResponseFormatStrategy.call()
                         ↓
          llm_client.chat_with_tools() / chat_with_response_format()
                         ↓
                    ❌ llm_client 没有这些方法！
                         ↓
          回退或报错
```

### 4.4 完整 Loop 流程（带问题标注）

```
用户输入: "帮我整理桌面文件"

初始化:
  conversation_history = [system, user(用户问题)]  ← 2条

┌─────────────────────────────────────────────────────────────────┐
│ Step 1                                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ① 第1次 LLM 调用 (Thought 阶段)                                  │
│     messages = [system, user]                                    │
│     LLM返回: "我看到桌面上有3个文件夹。\n使用工具: list_directory"│
│                                                                   │
│  ② 工具执行 (Action 阶段)                                        │
│     返回: ["文档", "图片", "下载"]                                │
│                                                                   │
│  ③ 添加 Observation                                               │
│     self._add_observation_to_history("Observation: success - ...")│
│     现状: [system, user, user(Observation)]                      │
│     ❌ 缺少 assistant(Thought)！                                  │
│                                                                   │
│  ④ 第2次 LLM 调用 (Observation 阶段)                             │
│     messages = [system, user, user(Observation)]  ← 错的！       │
│     ❌ LLM 看不到自己之前说的 "使用工具: list_directory"          │
│                                                                   │
│  ⑤ 添加 assistant(Thought) ← 太晚了！已经调用结束了               │
│     conversation_history = [system, user, user(Obs), assistant]   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Step 2                                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ① 第3次 LLM 调用 (Thought 阶段)                                  │
│     messages = [system, user, user(Obs), assistant(Thought)]      │
│     ❌ 还是有问题！第2次调用时的 messages 顺序是对的               │
│        但它是在 Step 1 结束后第244行才添加的                      │
│        也就是说第2次调用时缺少 assistant(Thought)                   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 五、如何正确地记录 Prompt

### 5.1 调用链分析

```
react_sse_wrapper.py
    ↓ 调用 agent.run_stream()
base_react.py: run_stream() 循环
    ↓ 调用 Hook
file_react.py: _on_before_loop()
    ↓ 调用 Hook
file_react.py: _on_after_loop()
```

### 5.2 记录点分析

| 文件 | 方法 | 状态 |
|------|------|------|
| react_sse_wrapper.py | start_request() | ✅ 创建日志，但被覆盖 |
| react_sse_wrapper.py | log_system_prompt() | ✅ 记录，但被覆盖 |
| react_sse_wrapper.py | log_task_prompt() | ✅ 记录，但被覆盖 |
| file_react.py | start_request() | ❌ 覆盖上面数据 |
| file_react.py | log_llm_call() | ✅ 从 _local 获取并追加 |
| file_react.py | log_llm_response() | ✅ 从 _local 获取并追加 |
| file_react.py | save() | ❌ 从未被调用 |

### 5.3 时序图（含设计实现说明）

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              Prompt 生成 & LLM 调用时序图（含设计实现）                            │
├───────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  【设计原理】                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ prompt_logger 使用【线程局部存储】保存数据：                                                   │  │
│  │   _local = threading.local()  ← 每个线程独立的数据                                           │  │
│  │                                                                                              │  │
│  │ 数据流：                                                                                       │  │
│  │   start_request() → 创建数据结构 → 保存到 _local.current_log                                │  │
│  │   log_xxx() → 从 _local 获取 → 追加数据                                                     │  │
│  │   save() → 从 _local 获取 → 写入 JSON 文件                                                │  │
│  └─────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                    │
│  【需求2：每次LLM调用时追加到文件】                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 每次 log_llm_call() 后立即调用 save()，追加本次调用内容：                                    │  │
│  │   - 本次调用的 Prompt 历史过程（messages 从2条→4条→6条...的累积）                            │  │
│  │   - 本次最终调用 LLM 的 Prompt（完整 messages）                                            │  │
│  └─────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                    │
├───────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                    │
│  react_sse_wrapper.py       base_react.py: run_stream()          prompt_logger(_local)              │
│  ───────────────          ───────────────────────────          ────────────────────                 │
│                                                                                                    │
│        │ start_request()                    │                                                    │
│        ├────────────────────────────────► │ ① 创建日志数据结构                                    │
│        │                                    │ ② 保存到 _local.current_log                        │
│        │                                    │                                                    │
│        │ log_system_prompt()                │                                                    │
│        ├────────────────────────────────► │ ③ 追加 Prompt组装过程                             │
│        │                                    │                                                    │
│        │ log_task_prompt()                  │                                                    │
│        ├────────────────────────────────► │ ④ 追加 Prompt组装过程                             │
│        │                                    │                                                    │
│        │                                    │ ┌─────────────────────────┐                         │
│        │                                    │ │ _on_before_loop()   │                         │
│        │                                    │ │ ❌又调用start_request│                         │
│        │                                    │ │   (覆盖_local数据!)│                         │
│        │                                    │ └─────────────────────────┘                         │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ┌─────────────────────────┐                         │
│        │                                    │ │ 第1次LLM调用        │                         │
│        │                                    │ │ type=thought, step=1  │                         │
│        │                                    │ │ messages=[sys,user] │                         │
│        │                                    │ │ =2条                │                         │
│        │                                    │ └─────────────────────────┘                         │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ◄─ log_llm_call()       │                         │
│        │                                    │    从_local获取→追加messages                       │
│        │                                    │ ◄─ log_llm_response()    │                         │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ◄─ save() 【需求2：立即写入文件】 │                         │
│        │                                    │    追加本次调用历史+最终Prompt                              │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ┌─────────────────────────┐                         │
│        │                                    │ │ 第2次LLM调用        │                         │
│        │                                    │ │ type=observation, step=1│                         │
│        │                                    │ │ messages=[sys,user, │                         │
│        │                                    │ │       asst,user]    │                         │
│        │                                    │ │ =4条                │                         │
│        │                                    │ └─────────────────────────┘                         │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ◄─ log_llm_call()       │                         │
│        │                                    │ ◄─ log_llm_response()    │                         │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ◄─ save() 【需求2：立即写入文件】 │                         │
│        │                                    │    追加本次调用历史+最终Prompt                              │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ┌─────────────────────────┐                         │
│        │                                    │ │ 第N次LLM调用...      │                         │
│        │                                    │ └─────────────────────────┘                         │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ◄─ save() 【需求2：立即写入文件】 │                         │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ┌─────────────────────────┐                         │
│        │                                    │❌│循环结束-没调用      │                         │
│        │                                    │  │_on_after_loop()      │                         │
│        │                                    │ └─────────────────────────┘                         │
│        │                                    │              │                                    │
│        │                                    │              ▼                                    │
│        │                                    │ ❌ save()从未被调用                               │
│        │                                    │                                                │
│        │                                    │ 【结果】                                        │
│        │                                    │ 每次LLM调用都追加到文件 ✅                        │
│        │                                    │ 但循环结束时最终save()没调用                      │
│        │                                    │                                                │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 六、实施计划

### 6.1 修复步骤

| 步骤 | 修复内容 | 对应问题 |
|------|---------|---------|
| 步骤1 | 删除 file_react.py:_on_before_loop() 中的 start_request() 调用 | P3 |
| 步骤2 | 在 file_react.py 的 log_llm_call() 后立即调用 save() | P4 |
| 步骤3 | 在 base_react.py:run_stream() 添加 finally 块调用 _on_after_loop() | P5 |
| 步骤4 | 调整 conversation_history 累积顺序：先添加 assistant，后添加 Observation | P1 |
| 步骤5 | 统一 SSE 事件结构：去掉 obs_ 前缀 | P2 |
| 步骤6 | 修复 llm_client 定义或修改策略调用方式 | P6, P7 |
| 步骤7 | TextStrategy 返回 JSON 格式 | P8 |
| 步骤8 | 修复 parsed_obs.content 保存问题：第244行应保存第2次LLM响应，不是第1次 | P14 |

### 6.2 P6+P7+P8 综合修复方案

**方案A：修改 llm_client 定义**

```python
# react_sse_wrapper.py
class LLMClientWrapper:
    def __init__(self, ai_service):
        self.ai_service = ai_service
    
    async def chat(self, message, history=None):
        return await self.ai_service.chat(message, history)
    
    async def chat_with_tools(self, message, history, tools):
        return await self.ai_service.chat_with_tools(message, history, tools)
    
    async def chat_with_response_format(self, message, history, response_format):
        return await self.ai_service.chat_with_response_format(message, history, response_format)
```

**方案B：修改策略调用方式**

```python
# file_react.py:_get_llm_response()
# 直接使用 ai_service，而不是通过 llm_client
if strategy.method == "tools":
    response = await self.ai_service.chat_with_tools(
        message=last_message,
        history=history_messages,
        tools=self.tools
    )
elif strategy.method == "response_format":
    response = await self.ai_service.chat_with_response_format(
        message=last_message,
        history=history_messages,
        response_format=self.response_format
    )
```

### 6.3 预期效果

修复后：
1. ✅ JSON 文件正常生成
2. ✅ 每次 LLM 调用后立即保存
3. ✅ 发送给 LLM 的 messages 顺序正确
4. ✅ SSE 事件结构统一
5. ✅ 策略选择和执行匹配
6. ✅ LLM 返回的 JSON 格式正确解析
7. ✅ parsed_obs.content 正确保存，LLM 能看到完整的对话历史

---

## 七、版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-03-29 05:08:14 | 小沈 | 初始版本 |
| v1.9 | 2026-03-29 13:45:00 | 小沈 | 补充需求2实现说明：每次LLM调用后立即save() |
| v1.12 | 2026-03-29 07:05:46 | 小沈 | 新增第六章：ReAct Loop机制深入分析，发现messages顺序错误的严重问题 |
| v1.13 | 2026-03-29 07:20:29 | 小沈 | 新增P6-P8问题：llm_client方法缺失、策略执行不匹配、TextStrategy返回格式问题 |
| v2.0 | 2026-03-29 07:30:00 | 小沈 | 重新梳理文档结构：需求→问题→记录策略→问题分析→实施计划 |
| v2.1 | 2026-03-29 07:31:04 | 小沈 | 调整章节标题：第四章改为"现有代码的ReAct Loop的问题和解决办法"，第五章改为"如何正确地记录Prompt" |
| v2.2 | 2026-03-29 15:45:00 | 小沈 | 验证小强补充的P9-P12问题：确认P9代码逻辑正确无需修复，P10风格问题，P11/P12确认有问题并更新优先级 |
| v2.3 | 2026-03-29 16:00:00 | 小沈 | 验证小强深度分析P13-P15：确认P13重复添加assistant、P14已排除、P15确认；修正P1描述为"重复添加assistant" |
| v2.4 | 2026-03-29 11:12:44 | 小沈 | 验证小健深度分析：确认P14问题存在（parsed_obs.content从未保存）；补充P14详细分析到4.2.9节 |

**文档结束**
