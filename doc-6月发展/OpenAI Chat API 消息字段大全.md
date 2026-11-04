# OpenAI Chat API 消息字段大全

**创建时间**: 2026-06-17 12:55:51  
**编写人**: 小沈  
**用途**: 全面记录OpenAI调用格式的消息类型和可用字段，用于FC(Tool Calling)场景

---

## 版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.1 | 2026-06-17 12:55:51 | 新增第三节完整请求格式（全部参数 + 结构化输出 + stream_options + tool_choice详解） | 小沈 |
| v1.0 | 2026-06-17 12:55:51 | 初始版本，完整字段说明 | 小沈 |

---

## 一、总览：messages 数组的消息类型

OpenAI Chat Completions API 的 `messages` 数组支持 **5种角色**：

| 角色 | 角色值 | 用途 | 出现位置 |
|------|--------|------|---------|
| 开发者 | `developer` | 替代 system，设置模型行为（o 系列模型推荐） | 第一条或开头 |
| 系统 | `system` | 设定 AI 助手的行为和上下文 | 通常是第一条 |
| 用户 | `user` | 用户输入 | 交替出现 |
| 助手 | `assistant` | 模型回复（含 tool_calls 时也有它） | 紧跟 user |
| 工具 | `tool` | 工具执行结果返回给模型 | 紧跟 assistant 的 tool_calls |

---

## 二、完整字段清单

### 2.1 `developer` 消息

```json
{
  "role": "developer",
  "content": "你是一个专业助手",
  "name": "optional_name"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role` | `"developer"` | ✅ | 开发者角色 |
| `content` | `string` 或 `array` | ✅ | 系统指令内容 |
| `name` | `string` | ❌ | 作者名称，用于区分多作者 |

**说明**:
- 2024年底新增，o1/o3 系列推荐使用 developer 替代 system
- 比 system 更强调"开发者指令"的语义
- 放在 messages 第一条

---

### 2.2 `system` 消息

```json
{
  "role": "system",
  "content": "你是一个专业助手",
  "name": "optional_name"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role` | `"system"` | ✅ | 系统角色 |
| `content` | `string` 或 `array` | ✅ | 系统指令内容 |
| `name` | `string` | ❌ | 作者名称 |

**说明**:
- 传统方式，gpt 系列模型推荐使用 system
- o 系列模型更推荐使用 developer

---

### 2.3 `user` 消息

```json
{
  "role": "user",
  "content": "你好",
  "name": "optional_user_name"
}
```

或者多模态内容：

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "这是什么？"},
    {"type": "image_url", "image_url": {"url": "https://..."}},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,...", "detail": "high"}},
    {"type": "input_audio", "input_audio": {"data": "base64...", "format": "wav"}}
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role` | `"user"` | ✅ | 用户角色 |
| `content` | `string` 或 `array` | ✅ | 文本或内容块数组 |
| `name` | `string` | ❌ | 作者名称 |

#### content 为 array 时的内容块类型

```json
{"type": "text", "text": "描述文字"}
```

```json
{"type": "image_url", "image_url": {"url": "URL或base64", "detail": "auto|low|high"}}
```

```json
{"type": "input_audio", "input_audio": {"data": "base64", "format": "wav|mp3"}}
```

| 内容块类型 | 字段 | 说明 |
|-----------|------|------|
| `text` | `text` | 纯文本内容 |
| `image_url` | `url` | 图片URL或base64 |
| `image_url` | `detail` | 分辨率：auto(默认)/low(低)/high(高) |
| `input_audio` | `data` | base64音频数据 |
| `input_audio` | `format` | 音频格式：wav/mp3 |

---

### 2.4 `assistant` 消息（最复杂的角色）

#### 2.4.1 纯文本回复

```json
{
  "role": "assistant",
  "content": "你好，有什么可以帮你的？",
  "name": "optional_name"
}
```

#### 2.4.2 带工具调用（Tool Calling / FC）

```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "get_weather",
        "arguments": "{\"location\": \"北京\"}"
      }
    },
    {
      "id": "call_def456",
      "type": "function",
      "function": {
        "name": "get_time",
        "arguments": "{\"timezone\": \"Asia/Shanghai\"}"
      }
    }
  ]
}
```

#### 2.4.3 拒绝回答

```json
{
  "role": "assistant",
  "content": null,
  "refusal": "抱歉，我不能回答这个问题"
}
```

#### 完整字段表

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role` | `"assistant"` | ✅ | 助手角色 |
| `content` | `string` 或 `null` | ✅ | 文本内容。**不能同时有 content 和 tool_calls** |
| `name` | `string` | ❌ | 作者名称 |
| `tool_calls` | `array` | ❌ | 模型发起的工具调用列表 |
| `refusal` | `string` 或 `null` | ❌ | 模型拒绝回答时的理由 |

#### `tool_calls[i]` 字段表

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | `string` | ✅ | 工具调用ID，**必须全局唯一**（tool 消息靠此配对） |
| `type` | `"function"` | ✅ | 固定值 `"function"` |
| `function.name` | `string` | ✅ | 工具名 |
| `function.arguments` | `string` | ✅ | **JSON字符串**（必须是字符串，不能直接传对象） |

**重要规则**:
- `content` 与 `tool_calls` **互斥**：有 tool_calls 时 content 必须为 null
- `arguments` **必须是 JSON 字符串**，不能是 dict 对象（在流式场景中逐步拼接）
- 支持**并行调用**：一次返回多个 tool_calls，各有一个独立 id
- 并行调用配合：需要 `parallel_tool_calls: true`（默认就是 true）

---

### 2.5 `tool` 消息

```json
{
  "role": "tool",
  "content": "22°C",
  "tool_call_id": "call_abc123"
}
```

```json
{
  "role": "tool",
  "content": "执行失败：权限不足",
  "tool_call_id": "call_abc123"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role` | `"tool"` | ✅ | 工具角色 |
| `content` | `string` | ✅ | 工具执行结果 |
| `tool_call_id` | `string` | ✅ | 对应 assistant.tool_calls[i].id |
| `name` | `string` | ❌ | 工具名称（部分模型需要此字段） |

**重要规则**:
- `tool_call_id` **必须**匹配前面 assistant 消息中某个 tool_calls[i].id
- 一个 tool 消息只能对应一个 tool_call_id（一对一）
- 如果有多个 tool_calls，需要多个 tool 消息按顺序排列
- content 为**字符串**，如果结果是结构化数据，建议 JSON 序列化成字符串

**示例：完整的一次 FC 调用**:

```
messages = [
  {"role": "system", "content": "你是天气助手"},
  {"role": "user", "content": "北京天气如何？"},
  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{\"location\": \"北京\"}"}}
  ]},
  {"role": "tool", "content": "22°C", "tool_call_id": "call_1"},
  {"role": "assistant", "content": "北京目前22°C，天气晴朗。"}
]
```

---

### 2.6 `function` 消息（已废弃，不建议使用）

```json
{
  "role": "function",
  "content": "22°C",
  "name": "get_weather"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role` | `"function"` | ✅ | 函数角色 |
| `content` | `string` | ✅ | 函数返回结果 |
| `name` | `string` | ✅ | 函数名称 |

**说明**:
- OpenAI 旧版 Function Calling 格式，已被 `tool` 消息取代
- 区别：function 用 `name` 配对，tool 用 `tool_call_id` 配对
- 新的 API 仍然兼容 function 格式，但建议用 tool

---

## 三、完整请求格式（全部可用参数）

### 3.1 最简格式（只有 model + messages）

```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你好"}
  ]
}
```

### 3.2 FC 场景典型格式

```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "北京天气如何？"},
    {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {
          "id": "call_1",
          "type": "function",
          "function": {
            "name": "get_weather",
            "arguments": "{\"location\": \"北京\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "content": "22°C",
      "tool_call_id": "call_1"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "获取城市天气",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {"type": "string", "description": "城市名"}
          },
          "required": ["location"]
        }
      }
    }
  ],
  "tool_choice": "auto",
  "parallel_tool_calls": true,
  "temperature": 0.7,
  "max_tokens": 4096,
  "stream": true
}
```

### 3.3 完整请求格式（全部参数）

```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "tools": [...],
  "tool_choice": "auto",
  "parallel_tool_calls": true,
  "temperature": 0.7,
  "top_p": 1.0,
  "n": 1,
  "stream": true,
  "stream_options": {"include_usage": true},
  "stop": ["\n\n"],
  "max_tokens": 4096,
  "max_completion_tokens": 4096,
  "presence_penalty": 0.0,
  "frequency_penalty": 0.0,
  "logit_bias": {"123": 100, "456": -100},
  "user": "user_abc123",
  "seed": 42,
  "response_format": {"type": "text"},
  "reasoning_effort": "medium",
  "store": true,
  "metadata": {"key": "value"},
  "modalities": ["text", "audio"],
  "audio": {"voice": "alloy", "format": "wav"}
}
```

### 3.4 参数详解

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `model` | `string` | ✅ | - | 模型名，如 `gpt-4o` |
| `messages` | `array` | ✅ | - | 对话消息数组 |
| `tools` | `array` | ❌ | `null` | 工具定义列表 |
| `tool_choice` | `string`或`object` | ❌ | `"auto"` | 工具选择策略 |
| `parallel_tool_calls` | `bool` | ❌ | `true` | 是否允许并行调用 |
| `temperature` | `number` | ❌ | `1.0` | 输出随机性 (0-2) |
| `top_p` | `number` | ❌ | `1.0` | 核采样 (0-1) |
| `n` | `integer` | ❌ | `1` | 生成几条回复 |
| `stream` | `bool` | ❌ | `false` | 是否流式输出 |
| `stream_options` | `object` | ❌ | `null` | 流式附加选项 |
| `stop` | `string`或`array` | ❌ | `null` | 停止标记 |
| `max_tokens` | `integer` | ❌ | `4096` | 最大 token 数（旧版参数） |
| `max_completion_tokens` | `integer` | ❌ | `4096` | 最大 token 数（o 系列推荐） |
| `presence_penalty` | `number` | ❌ | `0.0` | 话题重复惩罚 (-2 到 2) |
| `frequency_penalty` | `number` | ❌ | `0.0` | 词频惩罚 (-2 到 2) |
| `logit_bias` | `object` | ❌ | `null` | token 倾向性调整 |
| `user` | `string` | ❌ | `null` | 用户标识 |
| `seed` | `integer` | ❌ | `null` | 随机种子（固定种子可复现） |
| `response_format` | `object` | ❌ | `{"type": "text"}` | 响应格式控制 |
| `reasoning_effort` | `string` | ❌ | `null` | 推理强度：low/medium/high |
| `store` | `bool` | ❌ | `false` | 是否存入历史 |
| `metadata` | `object` | ❌ | `null` | 自定义元数据 |
| `modalities` | `array` | ❌ | `["text"]` | 响应模态：text/audio |
| `audio` | `object` | ❌ | `null` | 音频输出配置 |

### 3.5 `response_format` 详解

```json
// 文本格式（默认）
{"type": "text"}

// JSON 模式（必须在 system 里强调输出JSON）
{"type": "json_object"}

// JSON Schema 强约束（结构化输出 Stuctured Outputs）
{
  "type": "json_schema",
  "json_schema": {
    "name": "weather_response",
    "description": "天气响应的结构",
    "schema": {
      "type": "object",
      "properties": {
        "city": {"type": "string"},
        "temperature": {"type": "number"},
        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
      },
      "required": ["city", "temperature", "unit"],
      "additionalProperties": false
    },
    "strict": true
  }
}
```

### 3.6 `tool_choice` 详解

```json
// 让模型自己决定
"tool_choice": "auto"

// 不调任何工具
"tool_choice": "none"

// 必须调用一次工具（随便哪个）
"tool_choice": "required"

// 强制调用指定工具
"tool_choice": {"type": "function", "function": {"name": "get_weather"}}
```

### 3.7 `stream_options` 详解

```json
// 流式输出时额外控制
{"stream_options": {"include_usage": true}}
```

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `include_usage` | `bool` | `false` | 最后一个 chunk 是否包含 token 用量统计 |

### 3.8 结构化输出（Structured Outputs）

OpenAI 的结构化输出有两种方式：

| 方式 | 使用参数 | 说明 |
|------|---------|------|
| **response_format.json_schema** | `response_format` | 强制模型输出符合 JSON Schema 的响应 |
| **tool strict mode** | `function.strict: true` | 强制 tool_calls.arguments 严格遵循 JSON Schema |

```json
// 方式1：response_format 结构化
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "step",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "thought": {"type": "string"},
          "action": {"type": "string"},
          "params": {"type": "object"}
        },
        "required": ["thought", "action"],
        "additionalProperties": false
      }
    }
  }
}

// 方式2：tool strict mode
{
  "tools": [{
    "type": "function",
    "function": {
      "name": "execute",
      "strict": true,
      "parameters": {
        "type": "object",
        "properties": {
          "command": {"type": "string"}
        },
        "required": ["command"],
        "additionalProperties": false
      }
    }
  }],
  "tool_choice": {"type": "function", "function": {"name": "execute"}}
}
```

### 3.1 `tools` 参数（工具定义）

```json
[
  {
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "获取城市天气",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {"type": "string", "description": "城市名"},
          "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
        },
        "required": ["location"]
      },
      "strict": true
    }
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | `"function"` | ✅ | 固定值 |
| `function.name` | `string` | ✅ | 工具名，**全 messages 必须唯一** |
| `function.description` | `string` | ❌ | 描述（强烈建议填，影响模型判断准确度） |
| `function.parameters` | `object` | ❌ | JSON Schema 格式参数定义（建议填，否则模型不知道怎么调） |
| `function.strict` | `boolean` | ❌ | 是否启用严格模式（结构化输出），true 时 parameters 必须符合 strict schema 规范 |

### 3.2 `tool_choice` 参数

| 值 | 含义 |
|----|------|
| `"auto"` | 让模型自己决定是否调工具 |
| `"none"` | 不调任何工具 |
| `"required"` | **必须调一次工具**（强制调） |
| `{"type": "function", "function": {"name": "xxx"}}` | **强制调指定工具** |

### 3.3 `parallel_tool_calls` 参数

- `true`（默认）：允许一次返回多个 tool_calls
- `false`：一次最多返回一个 tool_call

### 3.4 `response_format` 参数

| 值 | 说明 |
|----|------|
| `{"type": "text"}` | 默认，纯文本回复 |
| `{"type": "json_object"}` | 强制输出 JSON（必须在 system 里说"输出JSON"） |
| `{"type": "json_schema", "json_schema": {...}}` | 强类型 JSON Schema 约束（结构化输出） |

---

## 四、关键规则总结

### 4.1 messages 序列规则

```
✅ 正确: user → assistant → tool → assistant
✅ 正确: user → assistant(tool_calls) → tool → assistant
✅ 正确: user → assistant(tool_calls) → tool → tool → assistant
❌ 错误: tool 前没有 assistant(tool_calls)
❌ 错误: tool_call_id 不匹配
❌ 错误: assistant 同时有 content 和 tool_calls
```

### 4.2 每条消息必须遵守

| 规则 | 说明 |
|------|------|
| **role 不能变** | 发的 role 是什么，API 接收时就是什么 |
| **content 不能缺** | system/user/tool 必须有 content |
| **tool_call_id 必须匹配** | tool 消息的 tool_call_id 必须在前面 assistant.tool_calls 中存在 |
| **arguments 必须是字符串** | 发出去前确保 `json.dumps(arguments)` |
| **id 必须全局唯一** | tool_calls[i].id 在整个 messages 里不重复 |

### 4.3 消息数量限制

| 模型 | 最大 token | 建议 |
|------|-----------|------|
| gpt-4o | 128K | 实际受 token 数限制 |
| gpt-4o-mini | 128K | 同上 |
| o1/o3 | 200K | 建议精简 messages |
| 一般建议 | - | 保留最近 20-40 条，超长 history 做摘要 |

---

## 五、流式（Stream）场景的特殊处理

### 5.1 tool_calls 是增量拼接的

流式场景下，`tool_calls` 是分多次 chunk 返回的：

```
第1个chunk: delta={"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "get_weather", "arguments": ""}}]}
第2个chunk: delta={"tool_calls": [{"index": 0, "function": {"arguments": "{\"loc"}}]}
第3个chunk: delta={"tool_calls": [{"index": 0, "function": {"arguments": "ation\": \"北京\"}"}}]}
```

处理方式：
- 靠 `index` 区分不同的 tool_call
- 同 index 的 `arguments` **字符串拼接**
- 同 index 的 `id` 只出现在第一个 chunk
- 完整后拼成：`{"location": "北京"}`

### 5.2 完整 tool_call 的判定

一个 tool_call 结束的条件：
- API 不再推送该 index 的增量
- 或者收到 `stop` 类型的 finish_reason

---

## 六、常见错误

| 错误 | 现象 | 原因 |
|------|------|------|
| 400 bad_request | "Invalid tool_call_id" | tool_call_id 不匹配 |
| 400 bad_request | "messages must be alternating" | 两个 user 连在一起 |
| 400 bad_request | "arguments must be a string" | 传了 dict 而不是 JSON 字符串 |
| 400 bad_request | "'content' and 'tool_calls' can't both be set" | assistant 同时有了 content 和 tool_calls |

---

**文件结束时间**: 2026-06-17 12:55:51
