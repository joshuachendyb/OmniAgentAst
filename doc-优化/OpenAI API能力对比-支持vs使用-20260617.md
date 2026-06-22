# OpenAI API能力对比：支持vs使用

**创建时间**: 2026-06-17 13:13:19  
**编写人**: 小沈  
**目的**: 对比OpenAI支持的所有能力，找出我们没用上的好东西

---

## 版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.1 | 2026-06-17 13:13:19 | 补充3.1节 function.examples字段（有示例时我们会附带） | 小沈 |
| v1.0 | 2026-06-17 13:13:19 | 初始版本，完整对比OpenAI API能力 | 小沈 |

---

## 一、请求参数对比（核心）

### 1.1 我们用到的参数（8个）

| 参数 | OpenAI支持 | 我们使用 | 使用位置 | 说明 |
|------|-----------|---------|----------|------|
| **model** | ✅ | ✅ | client_sdk.py:36 | 模型名 |
| **messages** | ✅ | ✅ | client_sdk.py:36 | 对话消息 |
| **tools** | ✅ | ✅ | client_sdk.py:46 | 工具定义 |
| **tool_choice** | ✅ | ✅ | llm_caller.py:52 | 工具选择策略（固定"auto"） |
| **stream** | ✅ | ✅ | client_sdk.py:44 | 流式输出 |
| **max_tokens** | ✅ | ✅ | base_service.py:53 | 最大token数 |
| **temperature** | ✅ | ✅ | base_service.py:54 | 输出随机性 |
| **seed** | ✅ | ✅ | base_service.py:55 | 随机种子 |

**使用代码**（client_sdk.py:25-49）：

```python
def _build_request_body(
    messages: List[Dict],
    model: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[str] = None,
    stream: bool = False,
) -> Dict:
    body = {"model": model, "messages": messages}
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature
    if seed is not None:
        body["seed"] = seed
    if stream:
        body["stream"] = True
    if tools:
        body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice
    return body
```

---

### 1.2 OpenAI支持但我们没用到的参数（18个）

| 参数 | OpenAI支持 | 我们使用 | 类型 | 默认值 | 说明 | 是否值得用 |
|------|-----------|---------|------|--------|------|-----------|
| **parallel_tool_calls** | ✅ | ❌ | bool | true | 是否允许并行调用多个工具 | ⭐⭐⭐ 强烈推荐 |
| **response_format** | ✅ | ❌ | object | {"type": "text"} | 结构化输出（JSON Schema） | ⭐⭐⭐ 强烈推荐 |
| **stream_options** | ✅ | ❌ | object | null | 流式选项（include_usage） | ⭐⭐ 推荐 |
| **reasoning_effort** | ✅ | ❌ | string | null | 推理强度（o系列专用） | ⭐⭐ 推荐 |
| **top_p** | ✅ | ❌ | number | 1.0 | 核采样（替代temperature） | ⭐ 可选 |
| **presence_penalty** | ✅ | ❌ | number | 0.0 | 话题重复惩罚（-2到2） | ⭐ 可选 |
| **frequency_penalty** | ✅ | ❌ | number | 0.0 | 词频惩罚（-2到2） | ⭐ 可选 |
| **logit_bias** | ✅ | ❌ | object | null | token倾向性调整 | ❌ 高级用法 |
| **stop** | ✅ | ❌ | string/array | null | 停止标记 | ⭐ 可选 |
| **n** | ✅ | ❌ | integer | 1 | 生成几条回复 | ❌ 不适用 |
| **user** | ✅ | ❌ | string | null | 用户标识（用于监控） | ⭐⭐ 推荐 |
| **metadata** | ✅ | ❌ | object | null | 自定义元数据 | ⭐ 可选 |
| **modalities** | ✅ | ❌ | array | ["text"] | 响应模态（text/audio） | ❌ 音频场景 |
| **audio** | ✅ | ❌ | object | null | 音频输出配置 | ❌ 音频场景 |
| **max_completion_tokens** | ✅ | ❌ | integer | 4096 | 最大token数（o系列推荐） | ⭐⭐ 推荐 |
| **store** | ✅ | ❌ | bool | false | 是否存入OpenAI历史 | ❌ 不需要 |
| **service_tier** | ✅ | ❌ | string | null | 服务层级（scale tier） | ❌ 企业功能 |
| **prediction** | ✅ | ❌ | object | null | 预测提示（降低延迟） | ❌ 高级用法 |

---

## 二、没用上的好东西（重点）

### 2.1 ⭐⭐⭐ parallel_tool_calls（强烈推荐）

**OpenAI说明**：
- 控制是否允许一次返回多个tool_calls
- 默认true（允许并行调用）
- 设为false可强制一次只返回一个tool_call

**我们当前状态**：
- ❌ 未使用
- 默认行为：允许并行调用

**为什么值得用**：
1. **某些场景需要串行执行**：
   - 工具之间有依赖关系（工具B依赖工具A的结果）
   - 资源竞争（同时操作同一文件）
   - 顺序敏感（先创建再修改）

2. **减少错误率**：
   - 并行调用时，LLM可能一次返回5个tool_calls
   - 如果其中3个失败，重试逻辑复杂
   - 串行调用更易控制

**使用示例**：

```python
# 场景1：文件操作必须串行（先读再写）
body["parallel_tool_calls"] = False

# 场景2：允许并行（查询多个独立数据源）
body["parallel_tool_calls"] = True
```

**建议**：
- 默认保持true（并行调用是性能优势）
- 提供配置项，允许用户按场景切换
- 文件操作类工具建议强制串行

---

### 2.2 ⭐⭐⭐ response_format（强烈推荐）

**OpenAI说明**：
- 强制模型输出符合指定格式
- 三种模式：
  1. `{"type": "text"}` - 默认，纯文本
  2. `{"type": "json_object"}` - 强制输出JSON
  3. `{"type": "json_schema", "json_schema": {...}}` - 强类型JSON Schema

**我们当前状态**：
- ❌ 未使用
- 依赖LLM自然输出，可能格式不规范

**为什么值得用**：

1. **JSON模式**（`json_object`）：
   - 强制LLM输出合法JSON
   - 无需在prompt里强调"输出JSON格式"
   - 减少解析错误

2. **JSON Schema模式**（`json_schema`）：
   - 强制LLM输出符合Schema
   - 字段名、类型、枚举值全部校验
   - 100%保证格式正确

**使用示例**：

```python
# 场景1：强制输出JSON（适用于返回结构化数据）
body["response_format"] = {"type": "json_object"}

# 场景2：强类型约束（适用于ReAct步骤输出）
body["response_format"] = {
    "type": "json_schema",
    "json_schema": {
        "name": "react_step",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string"},
                "action": {"type": "string"},
                "params": {"type": "object"}
            },
            "required": ["thought", "action"],
            "additionalProperties": False
        }
    }
}
```

**建议**：
- ReAct场景：用json_schema约束步骤格式
- 工具返回：用json_object保证返回JSON
- 普通对话：保持text模式

---

### 2.3 ⭐⭐ stream_options（推荐）

**OpenAI说明**：
- 流式输出的附加控制
- 目前只有一个选项：`include_usage`

**我们当前状态**：
- ❌ 未使用
- 流式输出时不返回token用量统计

**为什么值得用**：

```json
{
  "stream": true,
  "stream_options": {"include_usage": true}
}
```

**效果**：
- 最后一个chunk会包含token用量统计：
```json
{
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  }
}
```

**好处**：
1. **实时监控token消耗**
2. **按token计费场景必需**
3. **优化prompt长度**

**建议**：
- 流式场景默认开启
- 在最后一个chunk记录token用量
- 用于统计和监控

---

### 2.4 ⭐⭐ reasoning_effort（推荐）

**OpenAI说明**：
- o系列模型专用（o1/o3）
- 控制推理强度：low/medium/high
- 影响思考深度和耗时

**我们当前状态**：
- ❌ 未使用
- 使用o系列时无法控制推理强度

**为什么值得用**：

| 值 | 说明 | 适用场景 |
|----|------|---------|
| low | 快速推理，浅层思考 | 简单任务、快速响应 |
| medium | 平衡推理 | 一般任务（默认） |
| high | 深度推理，多轮思考 | 复杂任务、代码生成 |

**使用示例**：

```python
# 简单任务：快速响应
if model.startswith("o1") or model.startswith("o3"):
    body["reasoning_effort"] = "low"

# 复杂任务：深度思考
if task_complexity == "high":
    body["reasoning_effort"] = "high"
```

**建议**：
- 检测o系列模型时自动注入
- 根据任务复杂度动态调整
- 提供用户配置项

---

### 2.5 ⭐⭐ user（推荐）

**OpenAI说明**：
- 用户标识符
- 用于监控和滥用检测
- OpenAI后台可按user统计

**我们当前状态**：
- ❌ 未使用
- 无法区分不同用户

**为什么值得用**：

```python
body["user"] = "user_abc123"
```

**好处**：
1. **监控单个用户的API调用**
2. **防止单个用户滥用**
3. **按用户统计分析**
4. **OpenAI后台可查看**

**建议**：
- 从context获取user_id
- 传递给OpenAI用于监控
- 用于审计和统计

---

### 2.6 ⭐⭐ max_completion_tokens（推荐）

**OpenAI说明**：
- 新版参数，替代max_tokens
- o系列模型推荐使用
- 更精确控制输出长度

**我们当前状态**：
- ❌ 未使用
- 使用旧版max_tokens

**为什么值得用**：

```python
# o系列模型用新参数
if model.startswith("o1") or model.startswith("o3"):
    body["max_completion_tokens"] = 4096
else:
    body["max_tokens"] = 4096
```

**建议**：
- 检测o系列时用max_completion_tokens
- 其他模型用max_tokens
- 向前兼容

---

### 2.7 ⭐ top_p / presence_penalty / frequency_penalty（可选）

**OpenAI说明**：
- top_p：核采样（0-1），替代temperature
- presence_penalty：话题重复惩罚（-2到2）
- frequency_penalty：词频惩罚（-2到2）

**我们当前状态**：
- ❌ 未使用
- 仅用temperature控制随机性

**为什么值得用**：

1. **top_p vs temperature**：
   - temperature：调整概率分布的平滑度
   - top_p：直接截断低概率选项
   - 推荐：二选一，不要同时用

2. **presence_penalty**：
   - 惩罚已出现的话题
   - 鼓励模型谈论新话题
   - 适用于长对话、多轮对话

3. **frequency_penalty**：
   - 惩罚高频词
   - 减少重复用词
   - 适用于生成文本、写作

**使用示例**：

```python
# 减少重复话题（长对话场景）
body["presence_penalty"] = 0.6

# 减少重复用词（写作场景）
body["frequency_penalty"] = 0.5

# 使用top_p替代temperature
body["top_p"] = 0.9
body.pop("temperature")  # 不要同时用
```

**建议**：
- 长对话场景：加presence_penalty
- 写作场景：加frequency_penalty
- 提供配置项让用户调整

---

### 2.8 ⭐ stop（可选）

**OpenAI说明**：
- 停止标记
- 遇到指定字符串时停止生成
- 支持多个停止标记

**我们当前状态**：
- ❌ 未使用

**为什么值得用**：

```python
# 场景1：生成代码时遇到特定注释停止
body["stop"] = ["# END", "// END"]

# 场景2：生成列表时遇到空行停止
body["stop"] = ["\n\n"]
```

**建议**：
- 特定场景有用
- 一般场景不需要

---

## 三、工具定义参数对比

### 3.1 tools参数（我们用到的）

```json
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
    },
    "examples": [
      {"location": "北京"},
      {"location": "上海"}
    ]
  }
}
```

**我们用到的字段**：
- type ✅
- function.name ✅
- function.description ✅
- function.parameters ✅
- function.examples ✅（有示例时附带）

---

### 3.2 function 对象官方允许的字段清单

OpenAI 的 `function` 对象 **只支持4个官方字段**：

| 字段 | 类型 | 必填 | OpenAI官方 | 我们使用 | 说明 |
|------|------|------|-----------|---------|------|
| **name** | string | ✅ | ✅ 官方 | ✅ | 工具名称 |
| **description** | string | ❌ | ✅ 官方 | ✅ | 工具描述 |
| **parameters** | object | ❌ | ✅ 官方 | ✅ | JSON Schema参数定义 |
| **strict** | bool | ❌ | ✅ 官方 | ❌ | 启用严格模式 |
| **examples** | array | ❌ | ❌ **非官方** | ✅（有示例时附带） | 使用示例（部分兼容API支持如DeepSeek） |

**注意**：`examples` 不是 OpenAI 官方字段，但部分兼容 API（如 DeepSeek）支持。我们在 `to_openai_tools()` 中遇到 `meta.examples` 非空时会附带。

---

### 3.3 没用到的官方参数

唯一没用的官方参数：

#### function.strict

```json

```json
{
  "type": "function",
  "function": {
    "name": "execute",
    "strict": true,  // ← 启用严格模式
    "parameters": {
      "type": "object",
      "properties": {
        "command": {"type": "string"}
      },
      "required": ["command"],
      "additionalProperties": false  // strict模式必须
    }
  }
}
```

**效果**：
- 强制LLM输出的arguments严格符合Schema
- 100%保证格式正确
- 减少解析错误

**建议**：
- 所有工具默认开启strict模式
- 保证arguments格式正确
- 减少运行时错误

---

## 四、消息类型对比

### 4.1 我们用到的消息类型（4种）

| 角色 | OpenAI支持 | 我们使用 | 说明 |
|------|-----------|---------|------|
| **system** | ✅ | ✅ | 系统提示词 |
| **user** | ✅ | ✅ | 用户输入 |
| **assistant** | ✅ | ✅ | 模型回复（含tool_calls） |
| **tool** | ✅ | ✅ | 工具执行结果 |

---

### 4.2 没用到的消息类型

| 角色 | OpenAI支持 | 我们使用 | 说明 | 是否值得用 |
|------|-----------|---------|------|-----------|
| **developer** | ✅ | ❌ | o系列推荐替代system | ⭐⭐ 推荐 |

**developer说明**：
- 2024年底新增
- o1/o3系列推荐使用developer替代system
- 语义更清晰：开发者指令

**使用示例**：

```python
# o系列模型用developer
if model.startswith("o1") or model.startswith("o3"):
    messages.insert(0, {"role": "developer", "content": system_prompt})
else:
    messages.insert(0, {"role": "system", "content": system_prompt})
```

**建议**：
- 检测o系列时用developer
- 其他模型用system
- 向前兼容

---

## 五、总结：优先级排序

### 5.1 强烈推荐立即使用（⭐⭐⭐）

| 参数 | 好处 | 实施难度 | 优先级 |
|------|------|----------|--------|
| **parallel_tool_calls** | 控制并行/串行调用 | 低 | P0 |
| **response_format** | 强制输出格式 | 中 | P0 |
| **function.strict** | 保证arguments格式 | 低 | P0 |

---

### 5.2 推荐尽快使用（⭐⭐）

| 参数 | 好处 | 实施难度 | 优先级 |
|------|------|----------|--------|
| **stream_options** | 获取token用量统计 | 低 | P1 |
| **reasoning_effort** | 控制o系列推理强度 | 低 | P1 |
| **user** | 用户监控和统计 | 低 | P1 |
| **max_completion_tokens** | o系列推荐参数 | 低 | P1 |
| **developer消息** | o系列推荐角色 | 低 | P1 |

---

### 5.3 可选使用（⭐）

| 参数 | 好处 | 实施难度 | 优先级 |
|------|------|----------|--------|
| **top_p** | 替代temperature | 低 | P2 |
| **presence_penalty** | 减少话题重复 | 低 | P2 |
| **frequency_penalty** | 减少用词重复 | 低 | P2 |
| **stop** | 停止标记 | 低 | P2 |
| **metadata** | 自定义元数据 | 低 | P2 |

---

### 5.4 不推荐使用（❌）

| 参数 | 原因 |
|------|------|
| **logit_bias** | 高级用法，一般场景不需要 |
| **n** | 我们不需要多条回复 |
| **modalities/audio** | 暂不支持音频场景 |
| **store** | 不需要存入OpenAI历史 |
| **service_tier** | 企业功能 |
| **prediction** | 高级用法 |

---

## 六、实施建议

### 6.1 第一阶段（立即实施）

**修改client_sdk.py**：

```python
def _build_request_body(
    messages: List[Dict],
    model: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[str] = None,
    stream: bool = False,
    # 新增参数
    parallel_tool_calls: Optional[bool] = None,
    response_format: Optional[Dict] = None,
    stream_options: Optional[Dict] = None,
    user: Optional[str] = None,
) -> Dict:
    body = {"model": model, "messages": messages}
    
    # 原有参数
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature
    if seed is not None:
        body["seed"] = seed
    if stream:
        body["stream"] = True
    if tools:
        body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice
    
    # 新增参数
    if parallel_tool_calls is not None:
        body["parallel_tool_calls"] = parallel_tool_calls
    if response_format is not None:
        body["response_format"] = response_format
    if stream_options is not None:
        body["stream_options"] = stream_options
    if user is not None:
        body["user"] = user
    
    return body
```

---

### 6.2 第二阶段（工具strict模式）

**修改to_openai_tools**：

```python
def to_openai_tools(registry, categories=None, strict=True):
    tools = []
    for name, meta in sorted(registry._tools.items()):
        if not meta.expose_to_llm:
            continue
        func_def = {
            "name": meta.name,
            "description": meta.description,
            "parameters": meta.input_schema,
            "strict": strict,  # ← 新增
        }
        if meta.examples:
            func_def["examples"] = meta.examples
        tools.append({
            "type": "function",
            "function": func_def
        })
    return tools
```

---

### 6.3 第三阶段（o系列适配）

**检测o系列并注入特殊参数**：

```python
def _adapt_o_series(body, model):
    """o系列模型特殊适配"""
    if not (model.startswith("o1") or model.startswith("o3")):
        return body
    
    # 1. 用developer替代system
    if body["messages"] and body["messages"][0]["role"] == "system":
        body["messages"][0]["role"] = "developer"
    
    # 2. 用max_completion_tokens替代max_tokens
    if "max_tokens" in body:
        body["max_completion_tokens"] = body.pop("max_tokens")
    
    # 3. 默认推理强度
    if "reasoning_effort" not in body:
        body["reasoning_effort"] = "medium"
    
    return body
```

---

## 七、完整参数列表（参考）

### 7.1 请求参数（26个）

| 参数 | 类型 | 必填 | 默认值 | 我们使用 |
|------|------|------|--------|---------|
| model | string | ✅ | - | ✅ |
| messages | array | ✅ | - | ✅ |
| tools | array | ❌ | null | ✅ |
| tool_choice | string/object | ❌ | auto | ✅ |
| parallel_tool_calls | bool | ❌ | true | ❌ |
| stream | bool | ❌ | false | ✅ |
| stream_options | object | ❌ | null | ❌ |
| max_tokens | integer | ❌ | 4096 | ✅ |
| max_completion_tokens | integer | ❌ | 4096 | ❌ |
| temperature | number | ❌ | 1.0 | ✅ |
| top_p | number | ❌ | 1.0 | ❌ |
| n | integer | ❌ | 1 | ❌ |
| stop | string/array | ❌ | null | ❌ |
| presence_penalty | number | ❌ | 0.0 | ❌ |
| frequency_penalty | number | ❌ | 0.0 | ❌ |
| logit_bias | object | ❌ | null | ❌ |
| user | string | ❌ | null | ❌ |
| seed | integer | ❌ | null | ✅ |
| response_format | object | ❌ | text | ❌ |
| reasoning_effort | string | ❌ | null | ❌ |
| store | bool | ❌ | false | ❌ |
| metadata | object | ❌ | null | ❌ |
| modalities | array | ❌ | text | ❌ |
| audio | object | ❌ | null | ❌ |
| service_tier | string | ❌ | null | ❌ |
| prediction | object | ❌ | null | ❌ |

---

### 7.2 工具定义参数（含非官方字段）

| 参数 | 类型 | 必填 | OpenAI官方 | 我们使用 |
|------|------|------|-----------|---------|
| type | string | ✅ | ✅ | ✅ |
| function.name | string | ✅ | ✅ | ✅ |
| function.description | string | ❌ | ✅ | ✅ |
| function.parameters | object | ❌ | ✅ | ✅ |
| function.strict | bool | ❌ | ✅ | ❌ |
| function.examples | array | ❌ | ❌ 非官方 | ✅（有示例时附带） |

---

### 7.3 消息类型（5种）

| 角色 | 我们使用 |
|------|---------|
| system | ✅ |
| developer | ❌ |
| user | ✅ |
| assistant | ✅ |
| tool | ✅ |

---

## 版本历史

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-17 13:13:19 | 小沈 | 初始版本，完整对比OpenAI API能力 |