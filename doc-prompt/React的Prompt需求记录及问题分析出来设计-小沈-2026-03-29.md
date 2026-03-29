# React的Prompt需求记录及问题分析出来设计

**创建时间**: 2026-03-29 05:08:14 **版本**: v1.20 **编写人**: 小沈 **更新时间**: 2026-03-29 21:28:00

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

#### 4.2.9 P10: SSE事件type命名混乱（低）

**问题描述**

SSE 事件 type 命名不规范：
- thought：正确
- action_tool：应该改为 action（与 ReAct 框架一致）
- observation：正确
- chunk：正确

**影响**：不影响功能，只影响代码可读性。**可选修复**。

#### 4.2.10 P11: 错误处理导致LLM的content被丢弃（中等）

**问题位置**：`base_react.py` 第156-160行

```python
try:
    parsed = self.parser.parse_response(response)
except ValueError as e:
    logger.error(f"Failed to parse LLM response: {e}")
    self._add_observation_to_history(f"Parse error: {e}. Please respond with valid JSON format.")
    continue  # ← 跳过当前循环，LLM返回的content被丢弃！
```

**问题**：
- 如果 LLM 返回了有效的 content，但不是 JSON 格式
- parser 解析失败后，直接 continue
- **LLM 返回的完整 content 被丢弃，前端看不到 AI 的思考内容！**

**解决方案**：
```python
except ValueError as e:
    logger.error(f"Failed to parse LLM response: {e}")
    # 保存原始 response 到 conversation_history，避免丢弃
    self.conversation_history.append({"role": "assistant", "content": response})
    self._add_observation_to_history(f"Parse error: {e}. Please respond with valid JSON format.")
    continue
```

#### 4.2.11 P12: 历史消息裁剪_trim_history被注释（严重）

**问题位置**：`base_react.py` 第277-296行

```python
# [小沈 2026-03-28] 注释掉 - 不一定是真正原因，先去掉
# MAX_HISTORY_TURNS = 5  # 保留最近 N 轮对话

# [小沈 2026-03-28] 注释掉 - 不一定是真正原因，先去掉
# def _trim_history(self) -> None:
#     """限制对话历史长度，避免 token 爆炸导致 LLM 输出被截断"""
```

**问题**：
- `_trim_history()` 被注释掉，对话历史无限增长
- 多次循环后，conversation_history 可能包含几十条消息
- **LLM token 消耗爆炸，可能导致 LLM 输出被截断**
- **前端显示可能出现异常**

**解决方案**：
- 恢复 `_trim_history()` 函数
- 合理设置 `MAX_HISTORY_TURNS`（建议 5-10 轮）

#### 4.2.12 P13: 重复添加 assistant 到 conversation_history（中等）

**问题描述**

assistant 消息被重复添加：
1. **strategy 内部**：`llm_strategies.py` 可能添加一次
2. **base_react.py:244**：又添加一次

**后果**：
- conversation_history 中有重复的 assistant 消息
- LLM 可能看到重复的上下文
- token 消耗增加

**解决方案**：
- 确保只在一处添加 assistant
- 检查 strategy 内部是否重复添加

#### 4.2.13 P14: parsed_obs.content（第2次LLM响应）从未保存到conversation_history（严重）

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

#### 4.2.14 P16: parse错误后 continue 导致 SSE 事件不完整（中等）

**问题位置**：`base_react.py` 第158-160行

```python
try:
    parsed = self.parser.parse_response(response)
except ValueError as e:
    logger.error(f"Failed to parse LLM response: {e}")
    self._add_observation_to_history(f"Parse error: {e}. Please respond with valid JSON format.")
    continue  # ← 直接跳过，前端不会收到 thought 事件！
```

**问题**：
- parser 解析失败后，直接 continue
- **前端收不到 thought 事件（只有 observation 事件）**
- 用户看到的步骤列表不完整

**解决方案**：
```python
except ValueError as e:
    logger.error(f"Failed to parse LLM response: {e}")
    # 即使解析失败，也发送 thought 事件（使用原始 response）
    yield {
        "type": "thought",
        "step": step_count,
        "timestamp": create_timestamp(),
        "content": f"[解析失败] {response}",  # 显示原始 response
        "reasoning": "",
        "action_tool": "finish",
        "params": {}
    }
    self.conversation_history.append({"role": "assistant", "content": response})
    self._add_observation_to_history(f"Parse error: {e}. Please respond with valid JSON format.")
    continue
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

### 5.2 记录点分析（修正版）

| 文件 | 方法 | 问题 | 修复状态 |
|------|------|------|----------|
| react_sse_wrapper.py | start_request() | 创建日志，但被 file_react.py 覆盖 | ❌ P3 问题 |
| react_sse_wrapper.py | log_system_prompt() | 记录，但被覆盖 | ❌ P3 问题 |
| react_sse_wrapper.py | log_task_prompt() | 记录，但被覆盖 | ❌ P3 问题 |
| file_react.py | start_request() | 覆盖上面数据 | ❌ P3 问题，需删除 |
| file_react.py | _on_before_loop() | 调用 start_request()，导致数据覆盖 | ❌ P3 问题，需修复 |
| file_react.py | log_llm_call() | ✅ 从 _local 获取并追加 | ✅ 正常 |
| file_react.py | log_llm_response() | ✅ 从 _local 获取并追加 | ✅ 正常 |
| file_react.py | save() | 从未被调用，JSON 文件不生成 | ❌ P4 问题 |
| base_react.py | run_stream() 第213行 | 添加 Observation 顺序错误 | ❌ P1 问题 |
| base_react.py | run_stream() 第217行 | 第2次LLM调用时缺少 assistant | ❌ P1 问题 |
| base_react.py | run_stream() 第244行 | 保存 thought_content 而不是 parsed_obs.content | ❌ P14 问题 |
| base_react.py | run_stream() 第156-160行 | parse 失败后 continue，content 被丢弃 | ❌ P11/P16 问题 |
| base_react.py | _trim_history() | 被注释掉，对话历史无限增长 | ❌ P12 问题 |
| base_react.py | _on_after_loop() | 循环结束后未调用 | ❌ P5 问题 |

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

### 6.1 修复步骤（完整版）

| 步骤 | 修复内容 | 对应问题 | 优先级 | 完成状态 |
|------|---------|---------|--------|---------|
| **步骤1** | 删除 file_react.py:_on_before_loop() 中的 start_request() 调用 | P3 | P1 | ✅ 已完成 |
| **步骤2** | 在 file_react.py 的 log_llm_call() 后立即调用 save() | P4 | P1 | ✅ 已完成 |
| **步骤3** | 在 base_react.py:run_stream() 添加 finally 块调用 _on_after_loop() | P5 | P2 | ✅ 已完成 |
| **步骤4** | 调整 conversation_history 累积顺序：先添加 assistant，后添加 Observation | P1 | P0 | ✅ 已完成 |
| **步骤5** | 统一 SSE 事件结构：去掉 obs_ 前缀 | P2 | P1 | ✅ 已完成 |
| **步骤6** | 修复 llm_client 定义或修改策略调用方式 | P6, P7 | P0 | ✅ 已完成 |
| **步骤7** | TextStrategy 返回 JSON 格式 | P8 | P0 | ✅ 已完成 |
| **步骤8** | 修复 parsed_obs.content 保存问题：第244行应保存第2次LLM响应 | P14 | P0 | ✅ 已完成 |
| **步骤9** | 修复 parse 失败后的处理：保存原始 response 到 conversation_history | P11 | P1 | ✅ 已完成 |
| **步骤10** | 恢复 _trim_history() 函数，设置 MAX_HISTORY_TURNS=5 | P12 | P0 | ✅ 已完成 |
| **步骤11** | 检查 strategy 内部是否重复添加 assistant，确保只添加一次 | P13 | P1 | ✅ 已完成 |
| **步骤12** | parse 失败时也发送 thought 事件（使用原始 response） | P16 | P1 | ✅ 已完成 |
| **步骤13**（可选） | 统一 SSE 事件 type 命名：action_tool → action | P10 | P2 | ✅ 已完成 |

#### 6.1.1 深度检查结果（小健检查）

**检查时间**: 2026-03-29 16:42:40  
**检查人**: 小健  
**检查范围**: 步骤1-13的全部实现正确性和深度风险分析

| 步骤 | 检查项目 | 检查结果 | 风险分析 |
|------|---------|---------|---------|
| 步骤1 | 删除start_request()调用 | ✅ 正确 | 无风险，已完全移除 |
| 步骤2 | log_llm_call()后立即save() | ✅ 正确 | 确保JSON文件及时生成，无性能问题 |
| 步骤3 | finally块调用_on_after_loop() | ✅ 正确 | 确保session正确关闭，无资源泄漏 |
| 步骤4 | conversation_history顺序调整 | ✅ 正确 | 符合LLM期望的对话格式，提高上下文连贯性 |
| 步骤5 | 去掉obs_前缀 | ✅ 正确 | SSE事件结构统一，前端解析正常 |
| 步骤6 | LLMClientWrapper实现 | ✅ 正确 | 统一接口，扩展性好，无兼容性问题 |
| 步骤7 | TextStrategy返回JSON格式 | ✅ 正确 | 符合parser期望，避免解析错误 |
| 步骤8 | parsed_obs.content保存第2次LLM响应 | ✅ 正确 | 确保LLM看到完整对话历史，提高上下文理解 |
| 步骤9 | parse失败保存原始response | ✅ 正确 | 防止LLM内容丢失，保持对话连贯性 |
| 步骤10 | 恢复_trim_history()函数 | ✅ 正确 | 防止对话历史无限增长，避免token爆炸 |
| 步骤11 | strategy内部不重复添加assistant | ✅ 正确 | 消除重复添加，确保conversation_history正确 |
| 步骤12 | parse失败发送thought事件 | ✅ 正确 | 保持SSE事件完整性，前端可显示错误 |
| 步骤13 | SSE事件type统一为action | ✅ 正确 | 前端解析统一，代码一致性提升 |

**结论**: 步骤1-13全部实现正确，无重大风险，代码质量符合预期。所有修复均按设计文档要求完成。

### 6.1.2 Prompt记录流程示意图

**绘制时间**: 2026-03-29 16:53:49  
**绘制人**: 小沈  
**说明**: 根据优化后的代码逻辑，绘制Prompt记录的完整流程示意图

#### 流程示意图（ASCII简化版）

```
用户消息
    ↓
[react_sse_wrapper.py] ──→ intent_type != 'chat'? ──→ 是 ──→ start_request() 创建日志文件
    │                                              │
    │                                              ↓
    │                                        log_system_prompt(系统prompt + intent_type + confidence)
    │                                              ↓
    │                                        log_task_prompt(任务prompt + context)
    │
    └──→ 否 ──→ 跳过日志记录
    ↓
[分发到 FileReactAgent]
    ↓
[FileReactAgent.run_stream]
    ↓
[BaseAgent.run_stream] ──→ _on_before_loop() (空操作)
    ↓
┌─────────────────────────────────────────┐
│             ReAct 循环                   │
├─────────────────────────────────────────┤
│ Thought 阶段:                           │
│   _get_llm_response()                   │
│   │                                     │
│   ├──→ log_llm_call() 记录LLM调用        │
│   ├──→ save() 立即保存日志               │
│   ├──→ 调用LLM                          │
│   └──→ log_llm_response() 记录LLM返回    │
│                                         │
│ Action 阶段:                            │
│   执行工具                               │
│                                         │
│ Observation 阶段:                       │
│   生成observation_text                  │
│   │                                     │
│   └──→ log_observation() 记录观察结果    │
│                                         │
│ 循环判断:                               │
│   ├─ 未结束 → 继续循环                   │
│   └─ 结束 → 输出最终结果                 │
└─────────────────────────────────────────┘
```

#### 记录点说明

| 步骤 | 位置 | 记录内容 | 方法 | 说明 |
|------|------|---------|------|------|
| **1. 开始请求** | react_sse_wrapper.py:244-248 | 创建日志文件，基本信息 | `start_request()` | 仅当intent_type != "chat"时 |
| **2. 系统prompt** | react_sse_wrapper.py:252-257 | 系统prompt内容，intent_type，confidence | `log_system_prompt()` | 带details参数 |
| **3. 任务prompt** | react_sse_wrapper.py:258-261 | 任务prompt内容，context | `log_task_prompt()` | 包含intent_type和confidence |
| **4. LLM调用** | file_react.py:160-170 | 调用轮次，messages列表，模型，提供商，调用类型 | `log_llm_call()` | 记录完整的messages列表 |
| **5. 立即保存** | file_react.py:173 | 保存当前日志到文件 | `save()` | 每次LLM调用前保存 |
| **6. LLM返回** | file_react.py:244-249 | 调用轮次，返回内容，返回类型，结束原因 | `log_llm_response()` | 更新对应调用记录 |
| **7. 观察结果** | base_react.py:228-235 | 工具执行结果，工具名称，工具参数 | `log_observation()` | **新增记录点** |

#### 数据流向

```
用户消息 → 创建日志文件 → 记录系统prompt → 记录任务prompt
    ↓
进入ReAct循环
    ↓
记录LLM调用 → 保存日志 → 调用LLM → 记录LLM返回
    ↓
执行工具 → 记录观察结果 → 添加到对话历史
    ↓
循环结束 → 输出结果
```

#### 日志文件内容结构

每次请求生成一个JSON文件（`prompt_{message_id}+{timestamp}.json`），包含：

1. **基本信息**：时间戳、会话ID、用户消息ID、AI消息ID、用户消息、日志文件路径
2. **Prompt组装过程**：系统prompt、任务prompt、观察结果等步骤记录
3. **LLM调用记录**：每次LLM调用的详细记录（消息列表、返回结果等）

---

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
### 6.2.1 方案对比分析

| 维度 | 方案A：修改 llm_client 定义 | 方案B：修改策略调用方式 |
|------|---------------------------|------------------------|
| **修改位置** | react_sse_wrapper.py | file_react.py |
| **修改数量** | 新增 1 个类（~20行） | 修改 1 个函数（~10行） |
| **侵入性** | 中等：新增中间层 | 低：直接修改调用点 |
| **可维护性** | ✅ 好：统一接口，易于扩展 | ⚠️ 一般：策略逻辑分散 |
| **向后兼容** | ✅ 好：保留 llm_client 接口 | ❌ 差：直接依赖 ai_service |

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

### 6.4 TextStrategy 分层处理架构（C+A+B）【2026-03-29 小沈】

#### 6.4.1 问题背景

**P8 问题的错误修复**（早期版本）：

```python
# 错误的修复：无论LLM返回什么，都包装成 finish
return json.dumps({
    "content": content,
    "action_tool": "finish",  # 永远都是 finish！
    "params": {},
    "reasoning": None
}, ensure_ascii=False)
```

**问题**：
1. 无论 LLM 返回什么，都被包装成 `action_tool: "finish"`
2. LLM 返回的工具调用意图被完全丢弃
3. 无法提取纯文本中的工具调用

#### 6.4.2 三种策略的定位

| 策略 | 触发条件 | LLM 输出格式 | 返回处理 |
|------|---------|------------|---------|
| **ToolsStrategy** | LLM 支持 tools | `{tool_calls: [...]}` | 从 tool_calls 提取 |
| **ResponseFormatStrategy** | LLM 支持 response_format | JSON Schema 格式 | 解析 JSON |
| **TextStrategy** | 不支持上述两种 | **纯文本** | 需要**提取** action |

#### 6.4.3 分层处理架构设计

**方案关系分析**：

| 方案 | 作用 | 必要性 | 复杂度 |
|------|------|--------|--------|
| **方案C** | 预处理层：先用 ToolParser 尝试 | ⭐⭐⭐ 必须 | 低 |
| **方案A** | 正则提取层：增强中文支持 | ⭐⭐ 推荐 | 中 |
| **方案B** | 保底层：工具名匹配 | ⭐ 可选 | 高 |

**推荐方案**：综合使用 **方案C + 方案A + 方案B**

**执行顺序**：
```
方案C: ToolParser.parse_response()     → JSON 解析 + _extract_from_text
    ↓ 失败
方案A: _extract_from_text() 增强版   → 中文纯文本提取
    ↓ 失败
方案B: _extract_by_known_tools()     → 工具名保底匹配
    ↓ 失败
返回 finish，保留完整 content
```

#### 6.4.4 分层处理流程图【2026-03-29 更新】

```
LLM 返回 content
       ↓
┌─────────────────────────────────────┐
│ 情况0: content 为空                 │
│   → 返回 finish, content=""        │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ 方案C: ToolParser.parse_response()  │
│   ├─ JSON 解析成功 → 返回 action   │
│   └─ JSON 解析失败                 │
│       → 调用 _extract_from_text()   │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ 方案A: _extract_from_text() 增强版  │
│   ├─ 英文纯文本含 action → ✅ 提取  │
│   └─ 中文纯文本含 action → ✅ 提取  │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ 【新增 2026-03-29】                 │
│ 方案D: 总结性文本检测               │
│   ├─ 英文: "I will summarize..."   │
│   │        "I have found..."      │
│   └─ 中文: "根据以上结果"          │
│        "任务已完成"                 │
│   → 返回 finish，保留完整 content   │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ 方案B: _extract_by_known_tools()    │
│   ├─ 找到已知工具名 → 返回匹配工具 │
│   └─ 未找到 → 继续               │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ 无法提取                            │
│   → 返回 finish，保留完整 content   │
└─────────────────────────────────────┘
```

#### 6.4.5 支持的场景

| 场景 | 示例输入 | 处理方式 |
|------|---------|---------|
| JSON 标准格式 | `{"action_tool": "list_directory"}` | 方案C: ToolParser 解析 |
| Markdown JSON | `` ```json {"action_tool": ...} ``` `` | 方案C: ToolParser 解析 |
| 英文纯文本含 action | `I need to use list_directory tool` | 方案C: _extract_from_text |
| 中文纯文本含 action | `我会调用 list_directory 工具` | 方案A: 增强正则提取 |
| 工具名直接出现 | `我会用 list_directory 查看文件` | 方案B: 已知工具名匹配 |
| **LLM总结性文本【2026-03-29】** | `I will now summarize what I have found` | 返回 finish，保留 content |
| 纯文本不含 action | `文件已整理完成` | 返回 finish，保留 content |
| JSON 数组格式 | `[{"action_tool": "..."}]` | 方案C: ToolParser 解析 |
| 空内容 | `""` | 返回 finish, content="" |

#### 6.4.6 代码实现

**TextStrategy.call() 核心逻辑**：

```python
async def call(self, llm_client, message, history_dicts, conversation_history, **kwargs):
    # ... 调用 LLM 获取 content ...
    
    # 情况0: 空内容
    if not content:
        return self._make_result(content="", action_tool="finish", params={})
    
    # 方案C: 尝试 ToolParser.parse_response()
    from app.services.agent.tool_parser import ToolParser
    try:
        parsed = ToolParser.parse_response(content)
        return self._make_result(
            content=parsed.get("content", ""),
            action_tool=parsed.get("action_tool", "finish"),
            params=parsed.get("params", {})
        )
    except ValueError:
        pass  # 继续方案A/B
    
    # 方案B: 工具名保底匹配
    tool_result = self._extract_by_known_tools(content)
    if tool_result:
        return self._make_result(
            content=tool_result.get("content", content),
            action_tool=tool_result["action_tool"],
            params=tool_result.get("params", {})
        )
    
    # 无法提取，返回 finish
    return self._make_result(content=content, action_tool="finish", params={})
```

#### 6.4.7 ToolParser._extract_from_text() 增强（方案A）

**新增中文支持的正则**：

```python
action_patterns = [
    # 英文标准格式
    r'(?:action)["\']?\s*[:=]\s*["\']?([\w]+)["\']?',
    r'(?:use|call|execute)\s+(?:the\s+)?([\w]+)\s+(?:tool|function)?',
    # 英文格式变体
    r'(?:tool|function)\s*[:=]\s*["\']?([\w]+)["\']?',
    # 【方案A】中文纯文本支持
    r'(?:调用|使用|执行)\s+[\w]+',
    r'(?:工具\s*为|函数\s*为)([\w]+)',
    r'([\w]+)\s*(?:工具|函数|操作)',
    r'(?:先)?(?:列出|读取|搜索|创建|删除|移动)\s+([\w]+)',
    r'(?:我\s*(?:需要|要|会))?\s*调用\s+([\w]+)',
    r'(?:使用|调用)\s+([\w]+)',
]
```

#### 6.4.7.1 总结性文本检测【2026-03-29 小沈 新增】

**问题**：LLM 在 Function Calling 模式下返回纯文本（如 "I will now summarize..."）时，解析失败导致"无法解析LLM响应"错误。

**解决方案**：在 `_extract_from_text()` 末尾添加对总结性文本的检测：

```python
# 【修复 2026-03-29】处理 LLM 返回纯文本（如 "I will now summarize..."）的情况
# 当无法提取出结构化 action 时，检查是否是总结性文本，如果是则返回 finish
summarize_patterns = [
    # 英文总结
    r'(?:summarize|summary|I have found|I will)',
    # 中文总结
    r'(?:总结|已完成|任务完成|结束了)',
    r'(?:根据.*?结果|基于.*?内容|以上)',
    r'(?:D盘|E盘|C盘).*?(?:如下|目录|文件|内容)',
]
for pattern in summarize_patterns:
    if re.search(pattern, text, re.IGNORECASE):
        result["thought"] = text.strip()
        result["action"] = "finish"
        result["action_input"] = {}
        return result
```

**匹配模式说明**：

| 模式 | 含义 | 示例 |
|------|------|------|
| `summarize\|summary` | 英文总结 | `I will now summarize what I found` |
| `I have found\|I will` | 英文习惯 | `I have found the files` |
| `总结\|已完成\|任务完成` | 中文总结 | `根据以上结果，我已完成任务` |
| `根据.*?结果\|基于.*?内容` | 中文结果描述 | `根据目录内容，以下是D盘的文件` |
| `D盘\|E盘.*?目录` | 磁盘目录描述 | `D盘和E盘的目录如下：` |

#### 6.4.8 修改文件清单

| 文件 | 修改内容 | 提交信息 |
|------|---------|---------|
| `llm_strategies.py` | TextStrategy 重构为 C+A+B 分层处理 | `fix: TextStrategy分层处理架构C+A+B+增强中文提取-小沈-2026-03-29` |
| `tool_parser.py` | `_extract_from_text()` 添加中文支持 | 同上 |

#### 6.4.9 测试验证

```bash
# 单元测试
pytest tests/test_tool_parser.py -v
# 结果：17 passed

pytest tests/test_adapter.py -v
# 结果：49 passed
```

#### 6.4.10 结论

| 项目 | 结论 |
|------|------|
| **分层架构** | C + A + B 分层处理，每层有明确职责 |
| **中文支持** | 方案A增强了 `_extract_from_text()` 的中文提取能力 |
| **工具名保底** | 方案B提供已知工具名匹配作为最后保底 |
| **覆盖率** | 支持 8+ 种输入场景，无遗漏 |

---

## 七、React的Type字段完整分析

### 7.1 网络深度学习成果：Type字段的生成时机（LLM调用前还是调用后）

#### 7.1.1 重要概念区分：messages数组 vs type字段

> ⚠️ **必须首先明确的概念**：type字段不是给LLM的prompt内容，而是前端显示步骤类型的数据。

| 概念 | 用途 | 内容 | 数据流向 |
|------|------|------|---------|
| **messages数组** | 给LLM的prompt（输入） | system, user(任务), assistant(Thought), user(Observation) | 程序 → LLM |
| **type字段** | 前端显示的步骤类型（输出） | thought, action_tool, observation, chunk, final, start, error | 程序 → 前端UI |

**关键区别**：

| 维度 | messages数组 | type字段 |
|------|-------------|----------|
| **作用** | 让LLM理解对话上下文 | 让前端显示执行步骤 |
| **内容来源** | 程序组装后发给LLM | LLM返回或工具执行后填充 |
| **包含Observation** | ✅ user(Observation) - 注入给LLM | ✅ observation - 显示给用户 |
| **两者的Observation** | 是**同一个数据**的不同视角 | - |

**举例说明**：

```
【给LLM的messages数组】                    【前端显示的type字段】
system: "你是一个助手..."                   start: {model: "gpt-4", ...}
user: "帮我整理桌面文件"                    thought: {content: "我需要...", action_tool: "list_directory"}
assistant: "我需要查看文件"                 
user: "Observation: [文档, 图片]"           observation: {content: "看到3个文件夹", obs_summary: "..."}
                                           chunk: {content: "现在我看到..."}
assistant: "我来创建分类文件夹"              
user: "Observation: success"                action_tool: {tool_name: "create_directory", ...}
                                           final: {content: "已完成整理"}
```

**核心理解**：
- messages是程序组装好发给LLM的prompt
- type字段是程序解析LLM返回后，生成给前端显示的数据
- 两者的"observation"是**同一个执行结果**的两种用途：注入给LLM vs 显示给用户

#### 7.1.1.1 数据流向图（北京老陈提供）

```
数据流向图
                        【LLM】
                          ↑
           messages数组（给LLM的prompt）
           [system, user, assistant, observation]
                          ↑
                       【Agent程序】
                          ↓
           type字段（给前端显示的数据）
           [start, thought, action_tool, observation, chunk, final]
                          ↓
                       【前端UI】
```

**图解说明**：
1. **Agent程序**是核心枢纽，负责：
   - 组装 messages 数组发给 LLM（向上箭头）
   - 解析 LLM 返回，生成 type 字段给前端显示（向下箭头）

2. **messages数组**（向上箭头）：
   - 作用：让LLM理解对话上下文
   - 内容：system, user(任务), assistant(Thought), user(Observation)
   - 流向：Agent程序 → LLM

3. **type字段**（向下箭头）：
   - 作用：让前端显示执行步骤
   - 内容：start, thought, action_tool, observation, chunk, final
   - 流向：Agent程序 → 前端UI

**关键洞察**：
- **同一个数据，两种用途**：工具执行结果 → ①注入给LLM（作为user(Observation)） ②显示给用户（作为observation步骤）
- **Agent程序是桥梁**：连接LLM和前端UI，负责数据转换和流程控制

---

#### 7.1.2 学习来源

| 来源 | 内容 | 核心结论 |
|------|------|---------|
| **ReAct论文** | Yao et al., ICLR 2023 - "ReAct: Synergizing Reasoning and Acting in Language Models" | Thought/Action/Observation是交互式循环，不是一次性准备 |
| **LangChain实现** | create_react_agent + AgentExecutor | 使用Stop Sequence截断，防止LLM幻觉Observation |
| **Prompt Engineering Guide** | ReAct Prompting官方文档 | Thought→Action→Observation是顺序执行，每次调用LLM后才生成下一步 |

#### 7.1.3 核心结论

**问题**：React的Type字段是在LLM调用前组装给LLM，还是调用LLM后通过返回的信息来填充？

**准确答案**：**除start字段外，所有Type字段都是在LLM调用后或工具执行后填充的，不是调用前组装的**

> 注：这里的"Type字段"是指前端SSE事件的type类型，用于前端显示步骤类型，不是给LLM的prompt内容。

| Type | 生成时机 | 数据来源 | 证据 |
|------|---------|---------|------|
| **start** | LLM调用**前** | 框架生成（provider/model信息） | start_step.py:53 - 用户消息→LLM调用前生成 |
| **thought** | LLM调用**后** | LLM返回的推理文本 | LLM生成"Thought: I need to..." |
| **action_tool** | LLM调用**后** | LLM返回的动作指令 | LLM生成"Action: search(...)" |
| **observation** | 工具执行**后** | 程序执行工具返回的结果 | Python执行工具，注入真实结果 |
| **chunk** | LLM流式返回**后** | LLM返回的文本片段 | 流式输出的中间内容 |
| **final** | LLM返回finish**后** | LLM返回的最终答案 | LLM生成"Final Answer: ..." |

#### 7.1.4 ReAct循环流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ReAct 循环流程图（Agent程序视角）                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ① [Agent程序] 发送 messages 给 LLM                                    │
│       messages = [system, user, ...]                                    │
│       程序位置：base_react.py:run_stream()                               │
│                                                                         │
│   ② [LLM调用] LLM 处理并返回响应                                         │
│       ↓                                                                 │
│   ③ [Agent程序解析] 解析 LLM 返回的 Thought + Action                    │
│       程序位置：base_react.py:170-177 (parser.parse_response)           │
│       ⭐ 这里生成 type='thought' 和 type='action_tool'                   │
│       ⭐ 数据来源：【LLM调用后返回的内容】                                │
│                                                                         │
│   ④ [Agent程序执行] 执行 Action（工具调用）                              │
│       程序位置：base_react.py:189-204 (_execute_tool)                   │
│       ↓                                                                 │
│   ⑤ [Agent程序] 生成 Observation（工具执行结果）                         │
│       程序位置：base_react.py:206-241                                    │
│       ⭐ 这里生成 type='observation'                                     │
│       ⭐ 数据来源：【工具执行后返回的结果】                                │
│                                                                         │
│   ⑥ [Agent程序] 注入 Observation 到 messages，再次调用 LLM               │
│       程序位置：base_react.py:213-217 (_add_observation_to_history)     │
│       ↓                                                                 │
│   重复 ①-⑥ 直到 LLM 返回 Final Answer                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 7.1.5 关键证据：Stop Sequence机制

根据LangChain实现（AgentExecutor）：

```python
# 关键技术：Stop Sequence
# LLM生成 "Action: search("Neo")" 后，会自动继续生成 "Observation: Neo is..."
# 但这是LLM的幻觉！实际Observation应该由程序执行工具后返回

# 解决方案：设置 stop=["Observation:"]
response = llm.generate(history, stop=["\nObservation:"])

# 结果：LLM生成到 "Observation:" 就停止
# Python执行工具，获取真实的 Observation，追加到 history
# 再次调用 LLM
```

**这证明**：
1. Thought + Action 是 LLM 调用后返回的
2. Observation 是程序执行工具后注入的，**不是LLM生成的**
3. 所有 type 字段都是 **LLM调用后** 填充的数据

#### 7.1.6 总结

| 问题 | 答案 |
|------|------|
| start 是调用前还是调用后？ | **调用前** - 框架在LLM调用前生成 |
| Thought 是调用前还是调用后？ | **调用后** - LLM返回的内容 |
| Action 是调用前还是调用后？ | **调用后** - LLM在Thought中决定的 |
| Observation 是调用前还是调用后？ | **工具执行后** - 程序执行工具返回的结果 |
| chunk 是调用前还是调用后？ | **调用后** - LLM流式返回的片段 |

**核心结论**：**除start字段（框架在LLM调用前生成）外**，所有Type字段都是在 **LLM调用后** 或 **工具执行后** 填充的，**不是调用前组装给LLM的**。

---

## 八、Type字段核心字段总结（基于通用ReAct框架研究）

### 8.1 研究背景

**研究目的**：抛开我们系统的具体实现，基于通用ReAct框架的学习，总结每个Type字段必须的核心字段。

**研究方法**：学习100篇相关代码实现（ReAct、LangChain、RAGents、Agent Patterns等），总结通用ReAct框架中每个Type字段的核心字段。

**核心原则**：Type字段是LLM调用后或工具执行后填充的数据，不是调用前组装的。

### 8.2 Type字段核心字段总结

#### 8.2.1 **start** - 开始步骤

**生成时机**：LLM调用**前**（框架生成）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `model` | string | 使用的LLM模型名称 | ✅ 必须 |
| `provider` | string | LLM提供商（openai、anthropic等） | ✅ 必须 |
| `timestamp` | string/number | 开始时间戳 | ✅ 必须 |
| `session_id` | string | 会话ID | ✅ 必须 |
| `task` | string | 用户任务/问题 | ✅ 必须 |

**可选字段**：
- `agent_id`: Agent标识
- `max_steps`: 最大迭代步数
- `available_tools`: 可用工具列表

#### 8.2.2 **thought** - 思考步骤

**生成时机**：第1次LLM调用**后**（LLM响应）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `content` | string | 思考内容（LLM的推理过程） | ✅ 必须 |
| `action_tool` | string/null | 计划执行的工具名称（如果没有工具调用则为null） | ✅ 必须 |
| `params` | object | 工具调用参数（如果action_tool不为null） | ✅ 必须 |

**可选字段**：
- `reasoning`: 详细的推理过程
- `confidence`: 置信度（0-1）
- `plan`: 执行计划列表
- `next_steps`: 下一步计划

**字段关系**：
```
如果 action_tool == null:
    - 这是纯思考，没有工具调用
    - params 应该为空对象 {}
    - 可能是最终回答（thought+final合并）
    
如果 action_tool != null:
    - 这是思考+工具调用
    - params 必须包含工具调用参数
```

#### 8.2.3 **action_tool** - 工具执行步骤

**生成时机**：工具执行**后**（工具执行结果）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `tool_name` | string | 执行的工具名称 | ✅ 必须 |
| `tool_params` | object | 工具调用参数 | ✅ 必须 |
| `execution_status` | string | 执行状态（success/error） | ✅ 必须 |
| `execution_result` | any | 工具执行结果 | ✅ 必须 |
| `timestamp` | string/number | 执行时间戳 | ✅ 必须 |

**可选字段**：
- `execution_time_ms`: 执行耗时（毫秒）
- `summary`: 执行结果摘要
- `raw_data`: 原始数据
- `error_message`: 错误信息（如果执行失败）
- `retry_count`: 重试次数

**字段关系**：
```
execution_status 可能的值：
- "success": 成功执行
- "error": 执行失败
- "timeout": 执行超时
- "permission_denied": 权限不足

根据 execution_status 不同：
- 如果 "success": execution_result 必须有值
- 如果 "error": error_message 必须有值
```

#### 8.2.4 **observation** - 观察步骤

**生成时机**：第2次LLM调用**后**（LLM响应 + 工具执行结果）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `content` | string | 观察内容（LLM对工具结果的总结） | ✅ 必须 |
| `tool_result` | any | 原始工具执行结果 | ✅ 必须 |
| `tool_name` | string | 对应的工具名称 | ✅ 必须 |
| `is_finished` | boolean | 是否完成任务 | ✅ 必须 |
| `next_action` | string/null | 下一个动作（如果is_finished=false） | ✅ 必须 |

**可选字段**：
- `reasoning`: LLM对工具结果的推理
- `confidence`: 置信度（0-1）
- `summary`: 结果摘要
- `raw_data`: 原始数据

**字段关系**：
```
如果 is_finished == true:
    - content 应该是最终回答
    - next_action 应该为 null
    
如果 is_finished == false:
    - content 是对工具结果的观察和总结
    - next_action 是下一个计划的动作
```

#### 8.2.5 **chunk** - 流式输出步骤

**生成时机**：LLM流式返回**时**（LLM响应）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `content` | string | 文本片段内容 | ✅ 必须 |
| `delta` | string | 增量内容（相对于前一个chunk的增量） | ✅ 必须 |
| `is_final` | boolean | 是否是最后一个chunk | ✅ 必须 |
| `timestamp` | string/number | 时间戳 | ✅ 必须 |

**可选字段**：
- `index`: chunk序号
- `role`: 角色（assistant）
- `model`: 使用的模型
- `finish_reason`: 完成原因（stop/length/tool_calls等）

**字段关系**：
```
流式输出的逻辑：
1. 第一个chunk：content = delta
2. 后续chunk：content = 前一个content + delta
3. 最后一个chunk：is_final = true
```

#### 8.2.6 **final** - 最终回答步骤

**生成时机**：LLM返回finish**时**（LLM响应）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `content` | string | 最终回答内容 | ✅ 必须 |
| `timestamp` | string/number | 完成时间戳 | ✅ 必须 |
| `total_steps` | number | 总执行步骤数 | ✅ 必须 |
| `total_tokens` | number | 总使用token数 | ✅ 必须 |

**可选字段**：
- `reasoning`: 最终推理总结
- `sources`: 信息来源
- `confidence`: 最终置信度
- `usage`: 使用统计（token、时间等）
- `intermediate_steps`: 中间步骤摘要

**字段关系**：
```
final 是 ReAct 循环结束的标志：
- content 是对用户问题的最终回答
- total_steps 记录循环次数
- total_tokens 记录LLM调用消耗
```

#### 8.2.7 **error** - 错误步骤

**生成时机**：发生错误**时**（异常处理）

**必须的核心字段**：
| 字段 | 类型 | 说明 | 必需性 |
|------|------|------|--------|
| `error_type` | string | 错误类型 | ✅ 必须 |
| `error_message` | string | 错误信息 | ✅ 必须 |
| `timestamp` | string/number | 错误时间戳 | ✅ 必须 |
| `recoverable` | boolean | 是否可恢复 | ✅ 必须 |

**可选字段**：
- `stack_trace`: 堆栈跟踪
- `context`: 错误上下文
- `suggested_fix`: 建议修复
- `retry_suggestion`: 重试建议

**字段关系**：
```
error_type 可能的值：
- "max_steps_exceeded": 超过最大步数
- "llm_error": LLM调用错误
- "tool_error": 工具执行错误
- "parsing_error": 解析错误
- "network_error": 网络错误
- "permission_error": 权限错误
```

### 8.3 核心字段总结表

| Type | 必须的核心字段 | 字段说明 |
|------|---------------|----------|
| **start** | model, provider, timestamp, session_id, task | 框架生成，LLM调用前 |
| **thought** | content, action_tool, params | LLM响应，思考+工具调用 |
| **action_tool** | tool_name, tool_params, execution_status, execution_result, timestamp | 工具执行后 |
| **observation** | content, tool_result, tool_name, is_finished, next_action | 第2次LLM响应+工具结果 |
| **chunk** | content, delta, is_final, timestamp | LLM流式响应 |
| **final** | content, timestamp, total_steps, total_tokens | LLM最终回答 |
| **error** | error_type, error_message, timestamp, recoverable | 错误处理 |

### 8.4 字段生成时机总结

| Type | 生成时机 | 数据来源 |
|------|---------|---------|
| **start** | LLM调用**前** | 框架生成 |
| **thought** | 第1次LLM调用**后** | LLM响应 |
| **action_tool** | 工具执行**后** | 工具执行结果 |
| **observation** | 第2次LLM调用**后** | LLM响应 + 工具结果 |
| **chunk** | LLM流式返回**时** | LLM响应 |
| **final** | LLM返回finish**时** | LLM响应 |
| **error** | 发生错误**时** | 异常信息 |

### 8.5 研究成果应用建议

1. **前端渲染**：根据每个Type的核心字段设计前端组件
2. **数据存储**：设计数据库表结构时参考核心字段
3. **API设计**：定义SSE事件结构时使用核心字段
4. **测试用例**：基于核心字段设计测试用例
5. **文档规范**：作为系统设计的参考规范

**重要提醒**：
- 以上总结基于通用ReAct框架研究，抛开了具体系统实现
- 核心字段是**必须有的**，可选字段可以根据需求添加
- 不同框架可能有不同的字段命名，但核心字段本质相同

---

## 九、Type字段在当前系统的具体实现分析

> **说明**：本章分析Type字段在**当前系统**的具体实现，包括代码位置、数据来源等。之前的第7章为通用理论分析章节。

### 9.1 Type字段定义（前端）

根据 `frontend/src/utils/sse.ts` 第66行：

```typescript
type: "thought" | "action_tool" | "observation" | "chunk" | "final" | "error" | "incident" | "interrupted" | "start" | "paused" | "resumed" | "retrying";
```

### 9.2 Type字段分类

| 类别 | Type | 用途 |
|------|------|------|
| **内容步骤** | `start` | 开始步骤，记录模型信息 |
| | `chunk` | AI流式回复的内容片段 |
| | `final` | 最终回答 |
| **执行步骤** | `thought` | AI思考过程 |
| | `action_tool` | 工具调用 |
| | `observation` | 工具执行结果 |
| **异常步骤** | `error` | 错误 |
| | `incident` | 中断（包含interrupted/paused/resumed/retrying） |

### 9.3 Type字段生成时机分析（当前系统）

#### ✅ LLM调用**前**准备的数据（框架生成）

| Type | 生成位置 | 时机 | 数据来源 |
|------|---------|------|---------|
| **start** | `start_step.py:53` | 用户发送消息后，LLM调用前 | 框架生成，记录model/provider等信息 |

#### ✅ LLM调用**后**填充的数据

| Type | 生成位置 | 时机 | 数据来源 |
|------|---------|------|---------|
| **thought** | `base_react.py:170` | 第1次LLM调用后，解析响应时 | LLM返回的content+action_tool+params |
| **action_tool** | `base_react.py:194` | thought之后，工具执行后 | 工具执行结果+LLM决定的action |
| **observation** | `base_react.py:230` | 工具执行后，第2次LLM调用后 | 工具执行结果+第2次LLM返回的content |
| **chunk** | `chat_stream_query.py:190` | LLM流式返回时 | LLM返回的文本片段 |
| **final** | `base_react.py:182/251` | LLM返回finish时 | LLM返回的最终内容 |
| **error** | `base_react.py:260/269` | 发生错误时 | 错误信息 |

### 9.4 ReAct循环的时序图（当前系统）

```
┌─────────────────────────────────────────────────────────────────┐
│                      ReAct 循环时序图                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ① [框架] start 步骤                                            │
│     type='start'                                                │
│     时机：用户消息→LLM调用前                                     │
│     来源：框架生成                                               │
│                                                                 │
│  ② [LLM调用1] 第1次LLM调用                                      │
│     ↓                                                           │
│  ③ [LLM响应] type='thought'                                     │
│     时机：第1次LLM调用完成后                                     │
│     来源：LLM返回的content+action_tool+params                   │
│     ⭐ 这是【LLM调用后】填充的数据！                              │
│                                                                 │
│  ④ [工具执行] type='action_tool'                                │
│     时机：工具执行完成后                                         │
│     来源：工具执行结果+LLM决定的action                           │
│                                                                 │
│  ⑤ [LLM调用2] 第2次LLM调用（观察阶段）                           │
│     ↓                                                           │
│  ⑥ [LLM响应] type='observation'                                 │
│     时机：第2次LLM调用完成后                                     │
│     来源：工具执行结果+LLM返回的content                          │
│     ⭐ 这是【LLM调用后】填充的数据！                              │
│                                                                 │
│  ⑦ [流式输出] type='chunk'                                      │
│     时机：LLM流式返回时                                          │
│     来源：LLM返回的文本片段                                      │
│     ⭐ 这是【LLM调用后】填充的数据！                              │
│                                                                 │
│  ⑧ [结束] type='final'                                          │
│     时机：LLM返回finish时                                        │
│     来源：LLM返回的最终内容                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.5 关键结论（当前系统）

#### 结论1：thought 是 LLM调用后填充

```python
# base_react.py:152-177
response = await self._get_llm_response()  # LLM调用
parsed = self.parser.parse_response(response)  # 解析响应

yield {
    "type": "thought",
    "content": parsed.get("content", ""),     # ← 来自LLM响应
    "action_tool": parsed.get("action_tool"), # ← 来自LLM响应
    "params": parsed.get("params", {})        # ← 来自LLM响应
}
```

**结论**：thought 的 content、action_tool、params 都来自 LLM 响应，不是调用前准备的。

#### 结论2：action_tool 是工具执行后填充

```python
# base_react.py:189-204
execution_result = await self._execute_tool(action_tool, params)  # 工具执行

yield {
    "type": "action_tool",
    "content": action_tool,
    "execution_status": execution_result.get("status"),  # ← 工具执行结果
    "summary": execution_result.get("summary", ""),      # ← 工具执行结果
    "raw_data": execution_result.get("data")             # ← 工具执行结果
}
```

**结论**：action_tool 的 execution_status、summary、raw_data 来自工具执行结果。

#### 结论3：observation 是第2次LLM调用后填充

```python
# base_react.py:216-241
llm_response = await self._get_llm_response()  # 第2次LLM调用
parsed_obs = self.parser.parse_response(llm_response)  # 解析响应

yield {
    "type": "observation",
    "content": parsed_obs.get("content", ""),      # ← 来自第2次LLM响应
    "obs_action_tool": parsed_obs.get("action_tool"),  # ← 来自第2次LLM响应
    "obs_params": parsed_obs.get("params", {})     # ← 来自第2次LLM响应
}
```

**结论**：observation 的 content 来自第2次LLM响应，不是工具执行结果本身。

### 9.6 参考依据

| 来源 | 内容 | 链接 |
|------|------|------|
| **后端代码** | base_react.py:170-241 - Type字段生成位置 | backend/app/services/agent/base_react.py |
| **前端代码** | sse.ts:66 - Type字段定义 | frontend/src/utils/sse.ts |

### 9.7 总结表（当前系统）

| Type | 生成时机 | 数据来源 | LLM调用前/后 |
|------|---------|---------|-------------|
| **start** | LLM调用前 | 框架生成 | ⏱️ 调用前 |
| **thought** | 第1次LLM调用后 | LLM响应 | ✅ 调用后 |
| **action_tool** | 工具执行后 | 工具结果 | ✅ 调用后 |
| **observation** | 第2次LLM调用后 | LLM响应 | ✅ 调用后 |
| **chunk** | LLM流式返回时 | LLM响应 | ✅ 调用后 |
| **final** | LLM返回finish时 | LLM响应 | ✅ 调用后 |
| **error** | 发生错误时 | 错误信息 | - |

**核心结论**：除 `start` 外，所有Type字段都是 **LLM调用后** 填充的数据，不是调用前准备的。

---

## 十、版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-03-29 05:08:14 | 小沈 | 初始版本 |
| v1.1 | 2026-03-29 07:05:46 | 小沈 | 新增第六章：ReAct Loop机制深入分析，发现messages顺序错误的严重问题 |
| v1.2 | 2026-03-29 07:20:29 | 小沈 | 新增P6-P8问题：llm_client方法缺失、策略执行不匹配、TextStrategy返回格式问题 |
| v1.3 | 2026-03-29 07:30:00 | 小沈 | 重新梳理文档结构：需求→问题→记录策略→问题分析→实施计划 |
| v1.4 | 2026-03-29 07:31:04 | 小沈 | 调整章节标题：第四章改为"现有代码的ReAct Loop的问题和解决办法"，第五章改为"如何正确地记录Prompt" |
| v1.5 | 2026-03-29 11:12:44 | 小沈 | 验证小健深度分析：确认P14问题存在（parsed_obs.content从未保存）；补充P14详细分析到4.2.9节 |
| v1.6 | 2026-03-29 12:26:25 | 小沈 | 全面修正文档：补全P10-P13/P16详细分析到4.2.9-4.2.14节；修正第五章记录点分析；补全第六章修复步骤（步骤9-13） |
| v1.7 | 2026-03-29 12:32:45 | 小沈 | 记录最终决策：北京老陈决定采用方案A（修改llm_client定义），架构清晰便于扩展 |
| v1.8 | 2026-03-29 12:35:00 | 小沈 | 新增6.2.1-6.2.2节：P6+P7+P8两个修复方案的对比分析、优缺点、决策建议 |
| v1.9 | 2026-03-29 12:38:13 | 小沈 | 新增第七章：React的Type字段完整分析，明确各Type的生成时机和数据来源 |
| v1.10 | 2026-03-29 12:41:27 | 小沈 | 修正章节顺序：版本历史移到第八章（文档末尾），React的Type字段分析移到第七章 |
| v1.11 | 2026-03-29 12:50:00 | 小沈 | 新增7.1节：网络深度学习成果总结，准确回答Type字段是LLM调用后填充不是调用前组装（附ReAct论文+LangChain实现+Stop Sequence证据） |
| v1.12 | 2026-03-29 13:04:08 | 小沈 | 修正7.1节：补充start字段（LLM调用前生成），明确"除start外所有Type字段是LLM调用后填充"；优化表述准确性 |
| v1.13 | 2026-03-29 13:20:30 | 小沈 | 新增7.1.1节：重要概念区分（messages数组 vs type字段），明确两者用途和区别，小健建议-小沈整理 |
| v1.14 | 2026-03-29 13:25:29 | 小沈 | 北京老陈提供数据流向图，加入文档（7.1.1.1节）；更新7.1.4节ReAct循环流程图，明确标注"程序"就是Agent程序 |
| v1.15 | 2026-03-29 13:42:04 | 小沈 | 新增第九章：Type字段核心字段总结（基于通用ReAct框架研究），总结每个Type字段必须的核心字段 |
| v1.16 | 2026-03-29 13:50:24 | 小沈 | 修复章节顺序问题：删除重复的"八、版本历史"，重新编号章节（第八章改为Type字段总结，第九章改为版本历史） |
| v1.17 | 2026-03-29 14:05:47 | 小沈 | 重新组织文档逻辑：将7.2-7.8节（当前系统代码分析）移到文档最后（第九章），保持第七章为通用理论分析章节 |
| v1.18 | 2026-03-29 20:30:00 | 小沈 | 新增6.4节：TextStrategy分层处理架构（C+A+B），修复P8问题的错误修复，实现完整的分层处理支持多种输入场景 |
| v1.19 | 2026-03-29 21:25:00 | 小沈 | 新增6.4.7.1节：LLM总结性文本检测（Function Calling模式下返回纯文本的处理）；更新6.4.5支持场景表格新增"LLM总结性文本"场景 |
| v1.20 | 2026-03-29 21:28:00 | 小沈 | 更新6.4.4流程图新增方案D（总结性文本检测）分支；增强6.4.7.1中文总结性文本匹配模式（添加D盘/E盘目录描述等中文模式） |

**文档结束**
