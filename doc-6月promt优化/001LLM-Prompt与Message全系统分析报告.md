# LLM Prompt 与 Message 全系统分析报告

**创建时间**: 2026-06-10 15:17:04
**版本**: v1.1
**编写人**: 小沈
**审核人**: 小健
**分析范围**: 从用户输入到 LLM API 调用的完整 Prompt/Message 构建链路

---

## 版本历史

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-10 15:17:04 | 小沈 | 初始版本，全系统分析 |
| v1.1 | 2026-06-11 05:18:28 | 小健 | 全问题3轮复核+X原则评估+已修复验证+未修复最优方案 |

---

## 一、分析说明

### 1.1 分析目标

- 全面梳理系统给 LLM 发送的 Prompt 和 Message 的完整构建链路
- 识别每一环节的不合理之处、冗余、错误、遗漏
- 输出可执行改进建议

### 1.2 分析方法

1. 逐文件阅读全部 40+ 相关文件
2. 追踪数据流：`用户输入 → API → Agent → Prompt组装 → MessageBuilder → LLM SDK → HTTP请求`
3. 按5大模块归类分析：System Prompt、Task Prompt、Conversation History、LLM调用、Observation
4. 复查5遍交叉验证

### 1.3 分析文件清单

| 模块 | 文件 |
|------|------|
| **API入口** | `chat_stream_v2.py` |
| **SSE运行器** | `run_sse_stream.py` |
| **Agent工厂** | `agent_factory.py`, `agent_config.py` |
| **Agent核心** | `universal_agent.py`, `base_agent.py`, `agent_initializer.py` |
| **ReAct循环** | `react_cycle.py`, `initialize_run_state.py` |
| **Handler** | `action_handler.py`, `answer_handler.py`, `chunk_handler.py` |
| **Message管理** | `message_builder.py`, `message_utils.py` |
| **Prompt基类** | `base_prompt_template.py` |
| **Prompt子类** | `file_prompts.py`, `system_prompts.py`, `network_prompts.py`, `desktop_prompts.py`, `document_prompts.py`, `time_prompts.py` |
| **中间层** | `system_adapter.py`, `__init__.py` |
| **Observation** | `observation_formatter.py` |
| **LLM响应解析** | `parse_llm_response.py` |
| **LLM Core** | `llm_core.py` |
| **LLM SDK** | `client_sdk.py` |
| **Prompt日志** | `prompt_logger.py` |
| **工具相关** | `chat_stream.py`, `constants.py`, `time_utils.py` |

---

## 二、完整数据流（概览）

```
┌─────────────────────────────────────────────────────────────────────┐
│                        完整 Prompt/Message 数据流                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  用户输入 (chat_stream_v2.py:47)                                     │
│    │                                                                 │
│    ▼ detect_intent() → intent_type + candidates                      │
│    │                                                                 │
│    ▼ AgentFactory.create() → UniversalAgent                          │
│    │  └─ config.prompt_class = FileOperationPrompts (举例)           │
│    │                                                                 │
│    ▼ agent._initialize_run_state()                                   │
│    │  ├─ _get_system_prompt() → build_full_system_prompt()           │
│    │  │   = get_system_prompt() + OUTPUT_FORMAT + TOOL_CALL_RULES    │
│    │  │   + safety_reminder + rollback_instructions                  │
│    │  │   + avoid_repeat_rules + candidates_hint + cross_tool_hint   │
│    │  │                                                              │
│    │  ├─ _get_task_prompt() → get_task_prompt(task)                  │
│    │  │   = "Task: xxx\nCurrent time: yyy\n请完成...\n步骤..."       │
│    │  │                                                              │
│    │  └─ message_builder.init_history(sys_prompt, task_prompt)       │
│    │      = [{role:"system", content: sys_prompt},                   │
│    │         {role:"user", content: task_prompt}]                    │
│    │                                                                 │
│    ▼ run_react_cycle() → 每轮循环:                                   │
│    │                                                                 │
│    ┌─→ _process_single_step()                                        │
│    │   ├─ agent._call_llm() → _call_llm_fc_stream / text_stream     │
│    │   │  ├─ message_builder.trim_history()     ← 容量裁剪           │
│    │   │  ├─ messages = prepare_messages_for_llm()                   │
│    │   │  ├─ _build_executed_tool_summary()     ← system注入         │
│    │   │  └─ llm_client.request_stream(messages, tools)             │
│    │   │     └─ BaseAIService → LLMClient → POST /chat/completions  │
│    │   │                                                             │
│    │   ├─ parse_llm_response() → 解析                                  │
│    │   │                                                             │
│    │   └─ handler 分派                                                │
│    │      ├─ action_handler: message_builder.add_observation()       │
│    │      │  + add_assistant(llm_response)                            │
│    │      └─ answer_handler: agent.status = COMPLETED                │
│    │                                                                 │
│    └── 循环直到 status=COMPLETED/FAILED 或 max_steps 耗尽              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、System Prompt 构建（逐段分析）

### 3.1 构建入口

**文件**: `universal_agent.py:69-80` `_get_system_prompt()`

```python
def _get_system_prompt(self) -> str:
    base_prompt = self.prompts.build_full_system_prompt()  # ← 基类组装
    candidates_hint = self._build_candidates_hint()         # ← 候选意图提示
    cross_tool_hint = self._build_cross_tool_hint()         # ← 跨分类工具提示
    parts = [base_prompt]
    if candidates_hint: parts.append(candidates_hint)
    if cross_tool_hint: parts.append(cross_tool_hint)
    return "\n\n".join(parts)
```

### 3.2 基类组装顺序

**文件**: `base_prompt_template.py:171-210` `build_full_system_prompt()`

组装顺序如下：

| 顺序 | 段名 | 来源 | 是否分类特有 | 说明 |
|------|------|------|-------------|------|
| ① | `get_system_prompt()` | 子类实现 | ✅ 是 | 分类Agent角色定义 + 工具描述 + Examples |
| ② | `OUTPUT_FORMAT` | 基类常量 | ❌ 否 | JSON输出格式（含退出规则） |
| ③ | `TOOL_CALL_RULES` | 基类常量 | ❌ 否 | 工具调用规则 |
| ④ | `get_safety_reminder()` | 子类覆盖 | ✅ 是 | 安全提醒（默认空） |
| ⑤ | `get_rollback_instructions()` | 基类方法 | ❌ 否 | 回滚说明（中英混用） |
| ⑥ | `avoid_repeat_rules` | 基类硬编码 | ❌ 否 | 避免重复规则（避免同一命令重复执行） |

### 3.3 各分类 get_system_prompt() 内容对比

所有子类的 `get_system_prompt()` 都包含三段：

```
① system_adapter 中间层: 【当前系统】+【路径格式】（可选【命令格式】）
② 本分类工具描述（硬编码或动态生成）
③ Tool Call Examples（4-6个JSON示例）
```

| 分类 | 文件 | 工具描述方式 | Examples数 | 额外内容 |
|------|------|-------------|-----------|---------|
| **file** | `file_prompts.py:37` | 动态 `build_tool_descriptions()` | 4 | 互斥参数规则 + write_text_file text规则 |
| **system** | `system_prompts.py:67` | 动态 `_build_tool_descriptions()` | 6 | 含shell/network等多分类示例 |
| **network** | `network_prompts.py:19` | 硬编码 | 4 | 无特殊 |
| **desktop** | `desktop_prompts.py:20` | 硬编码 | 4 | 无特殊 |
| **document** | `document_prompts.py:20` | 硬编码 | 4 | 无特殊 |
| **time** | `time_prompts.py:28` | 硬编码 | 4 | 无特殊 |

### 3.4 System Prompt 最终内容示例（file分类）

```
【当前系统】
Windows

【路径格式】
- 当前系统: C:\Users\xxx\file.txt 或 C:/Users/xxx/file.txt

【路径规则】
- 必须使用绝对路径...

# File Operation Tools

  以下是 FILE 分类下的 11 个工具:
  1. read_file - Read file content
     - When to use: 当需要Read file content时
     ...

【Tool Call Examples】:
Example 1: 读取文件
{"thought": "...", ...}

【Response Format - 必须遵守】:
必须使用JSON格式输出...

【Tool Call Rules - 极其重要】:
- 确认用户意图后,立即调用对应工具...

【避免重复规则】
- 同一命令/URL成功后不要重复执行...

【候选意图】用户任务可能属于以下分类: ...
```

**整个 System Prompt 的段数**: 7段（分类特有 + OUTPUT_FORMAT + TOOL_CALL_RULES + safety + rollback + avoid_repeat + candidates/cross_tool）

---

## 四、Task Prompt 构建

### 4.1 构建入口

**文件**: `base_prompt_template.py:126-141` `get_task_prompt(task)`

```python
def get_task_prompt(self, task: str) -> str:
    from app.utils.time_utils import now_str
    time_str = now_str()
    domain = self._get_domain_name()        # 如 "文件管理"
    steps = self._get_domain_steps()        # 如 "1. 分析... 2. 使用... 3. 总结"
    extra = self._get_domain_extra_notes()  # 分类额外提示
    parts = [
        f"Task: {task}",
        f"\nCurrent time: {time_str}",
        f"\n请完成此{domain}任务,按以下步骤:",
        steps,
    ]
    if extra:
        parts.append(f"\n{extra}")
    return "\n".join(parts)
```

### 4.2 实际内容示例

```
Task: 读取桌面上的config.json文件
Current time: 2026-06-10 15:00:00

请完成此文件管理任务,按以下步骤:
1. 分析需要做什么操作
2. 使用合适的工具完成任务
3. 用中文总结结果

Remember:
- 不要将思考内容传入text参数
- text参数必须是实际的文件内容
```

### 4.3 各分类 domain 值

| 分类 | _get_domain_name | _get_domain_steps |
|------|-----------------|-------------------|
| file | 文件管理 | 3步 |
| system | 系统信息 | 3步 |
| network | 网络 | 3步 |
| desktop | 桌面操作 | 3步 |
| document | 文檔处理 | 3步 |
| time (基类默认) | 通用 | 3步 |

---

## 五、Conversation History 管理

### 5.1 数据结构

**文件**: `message_builder.py:45-48`

```python
self.conversation_history: List[Dict] = []  # 正式历史
self.temp_history: List[Dict] = []           # 临时缓存(chunk累积用)
```

### 5.2 消息类型

| role | 来源 | content值 | 说明 |
|------|------|-----------|------|
| `system` | init_history() 第1条 | 完整System Prompt | 始终在第1位 |
| `user` | init_history() 第2条 | Task Prompt | 始终在第2位 |
| `assistant` | add_assistant() | LLM返回的JSON文本 | 每轮追加 |
| `user` + `[Tool Result]` | _append_observation() text策略 | 带 `[Tool Result]` 前缀 | observation文本 |
| `assistant` + `tool_calls` | _append_observation() FC协议 | content=None | FC协议工具调用 |
| `tool` | _append_observation() FC协议 | observation文本 | FC协议工具结果 |
| `system` | react_cycle.py:102 工具提醒 | `_TOOL_REMINDER` 常量 | 无工具调用时的提醒 |
| `system` | _call_llm() | 已执行工具摘要 | 每次调用注入 |

### 5.3 初始化

**文件**: `initialize_run_state.py:15-34`

```python
self.message_builder.init_history(sys_prompt, task_prompt)
# → conversation_history = [
#     {"role": "system", "content": sys_prompt},
#     {"role": "user", "content": task_prompt}
#   ]
```

### 5.4 每轮变化

```
第0轮: [system, user]
第1轮: [system, user, assistant(LLM响应1), tool/user+[Tool Result](observation1)]
第2轮: [system, user, assistant(LLM响应1), tool(obs1), assistant(LLM响应2), tool(obs2)]
...
```

### 5.5 prepare_messages_for_llm()

**文件**: `message_builder.py:120-133`

```python
def prepare_messages_for_llm(self):
    messages = list(self.conversation_history)
    if self.temp_history:
        messages = messages + list(self.temp_history)
    self._cap_temp_history()  # temp_history 字符限制 <=50000
    return messages
```

### 5.6 _call_llm() 注入已执行工具摘要

**文件**: `universal_agent.py:126-144`

```python
async def _call_llm(self):
    self.message_builder.trim_history()
    messages = self.message_builder.prepare_messages_for_llm()
    
    executed_summary = self._build_executed_tool_summary()
    if executed_summary:
        messages.append({"role": "system", "content": executed_summary})
    
    openai_tools = self._get_openai_tools()
    if openai_tools:
        async for item in self._call_llm_fc_stream(messages, openai_tools):
            yield item
    else:
        async for item in self._call_llm_text_stream(messages):
            yield item
```

已执行工具摘要内容示例:
```
【已执行工具(勿重复)】read_file→success|路径:D:/config.json; search_files→success|结果:2个文件
注意:上述工具已成功执行,结果已在Observation中,禁止再次调用!
```

### 5.7 历史裁剪 trim_history()

**条件**: 总字符 > MAX_CONTEXT_CHARS * 0.8（即 > 120000字符）

**裁剪策略**:
1. observation 去重（基于MD5指纹）
2. 保留最后10条 assistant 消息
3. 保留最后30条 observation
4. 从最旧 observation 开始截断直到 <= MAX_CONTEXT_CHARS * 0.7
5. FC配对完整性修复（assistant.tool_calls ↔ tool 配对）

---

## 六、LLM 调用链路

### 6.1 调用栈

```
universal_agent._call_llm()
  ├─ _call_llm_fc_stream()  (有 tools 时)
  │   └─ llm_client.request_stream(messages, mode="tools", tools=...)
  │       └─ BaseAIService.request_stream()
  │           └─ LLMClient.request_stream()
  │               └─ POST /chat/completions {model, messages, tools, tool_choice}
  │
  └─ _call_llm_text_stream() (无 tools 时)
      └─ llm_client.request_stream(messages, mode="text")
          └─ BaseAIService.request_stream()
              └─ LLMClient.request_stream()
                  └─ POST /chat/completions {model, messages}
```

### 6.2 请求体构建

**文件**: `client_sdk.py:25-50` `_build_request_body()`

```python
def _build_request_body(messages, model, mode, ...):
    body = {"model": model, "messages": messages}
    if max_tokens: body["max_tokens"] = max_tokens
    if temperature: body["temperature"] = temperature
    if seed: body["seed"] = seed
    if stream: body["stream"] = True
    if mode == "tools" and tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    return body
```

### 6.3 FC模式（有tools时）vs Text模式（无tools时）

| 维度 | FC模式 | Text模式 |
|------|--------|---------|
| **请求体** | `{messages, tools, tool_choice:"auto"}` | `{messages}` |
| **LLM响应** | delta.tool_calls 流 | delta.content 流 |
| **解析** | SSE流聚合tool_calls → JSON | 纯文本JSON解析 |
| **降级** | 流失败 → _call_llm_text_nostream | 流失败 → _call_llm_text_nostream |

---

## 七、不合理之处与改进建议

### 7.1 ❌ System Prompt 中 observation_formatter.get_observation_prompt() 未使用

**文件**: `base_prompt_template.py:152-154`

```python
def get_observation_prompt(self, observation: str) -> str:
    return f"Observation: {observation}\n\n"
```

**问题**: 这个方法是 `BasePrompts` 的成员方法，但实际 observation 是由 `observation_formatter.py` 的 `format_llm_observation()` 生成，且 `file_prompts.py:111-143` 子类覆盖了此方法。但 **没有任何地方调用 `get_observation_prompt()`** —— observation 文本由 `message_builder._normalize_observation_prefix()` 处理前缀，不是通过 prompt 类。

**影响**: 死代码，误导维护者。

**建议**: 删除 `BasePrompts.get_observation_prompt()` 及其子类覆盖。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ✅ 已修复 — 该方法和 file_prompts.py 中的子类覆盖已在 commit 90c30e5a 中删除
- grep 确认当前代码库无 `get_observation_prompt` 引用
- 原问题描述准确属实

**第2轮: 10大原则验证**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| ISP接口隔离 | ✅ | 删除无用方法后接口更精简 |
| YAGNI不过度设计 | ✅ | 死代码正是YAGNI反例 |
| 禁止backward compatibility | ✅ | 无调用方,删除无影响 |

**第3轮: 修复确认**
- 🏆 已执行方案: 删除 BasePrompts.get_observation_prompt() + file_prompts.py 子类覆盖
- commit: `90c30e5a refactor: 删除prompt层死代码+Prompt优化`
- 验证: 编译通过 + 测试通过

---

### 7.2 ❌ System Prompt 中 get_parameter_reminder() 未使用

**文件**: `base_prompt_template.py:160-162`

```python
def get_parameter_reminder(self) -> str:
    return ""
```

**问题**: 所有5个子类都覆盖了此方法（`file_prompts.py`, `system_prompts.py`, `network_prompts.py`, `desktop_prompts.py`, `document_prompts.py`），但 `build_full_system_prompt()` 已明确注释"已去掉,由方案C(_tools_to_schema_text)替代"（第19行注释）。此方法及相关代码完全没有被执行。

**影响**: 大量死代码。每个子类都写了10-20行的 parameter_reminder，永远不会被调用。

**建议**: 删除 `get_parameter_reminder()` 抽象方法及其所有子类实现。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ✅ 已修复 — 该抽象方法+6个子类覆盖已在 commit 90c30e5a 中删除
- grep 确认当前代码库无 `get_parameter_reminder` 引用(基类注释提及"已删除"除外)
- 原问题描述准确,是最大规模的死代码(7个文件,共~120行)

**第2轮: 10大原则验证**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| ISP接口隔离 | ✅ | 基类接口精简,子类不需覆盖无用方法 |
| DRY不重复 | ✅ | 7个同名方法本身就违反DRY(构造相似的reminder) |
| YAGNI不过度设计 | ✅ | 方案C(_tools_to_schema_text)已替代此功能 |

**第3轮: 修复确认**
- 🏆 已执行方案: 删除 BasePrompts.get_parameter_reminder() + 6个子类(file/time/network/document/desktop/system)覆盖
- commit: `90c30e5a refactor: 删除prompt层死代码+Prompt优化`
- 验证: 编译通过 + 测试通过

---

### 7.3 ❌ System Prompt 结构缺少统一 schema/text 切换时的字段说明

**问题**: 当 `_call_llm_fc_stream()` 的 `mode="tools"` 时，API 通过 `tools` 数组提供工具 Schema。但当降级到 `_call_llm_text_stream()` 时，System Prompt 中没有工具的 JSON Schema 描述（只有 `TOOL_CALL_RULES` 的通用规则和分类下的示例），LLM 可能不知道参数的精确格式。

**具体举例**: 
- FC 模式：tools=[{"type":"function","function":{"name":"read_file","parameters":{...}}}]
- Text 模式：只有 "1. read_file - Read file content\n   - Parameters: file_paths" 这样简单的参数名列表，没有参数类型、是否必填等 Schema 信息

**影响**: Text 模式下 LLM 可能漏填必填参数、填错参数类型。

**建议**: 在 System Prompt 的 OUTPUT_FORMAT 或 TOOL_CALL_RULES 中增加工具参数的 JSON Schema 描述（精简版），或者在 Text 模式降级时注入 schema 信息（`inject_schema_text()` 已在 `message_utils.py` 中有定义但未被 `_call_llm_text_stream` 调用）。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ✅ 已修复 — `build_tool_descriptions()` 现已为每个参数输出 type/required/description
- 当前输出示例: `path(string)(必填):文件路径`
- 原问题描述准确: Text模式之前只有参数名列表

**第2轮: 10大原则验证**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| SRP单一职责 | ✅ | 工具描述函数本就应该包含参数信息 |
| KISS保持简单 | ✅ | 遍历input_schema.get('properties')拼装 |
| YAGNI不过度设计 | ✅ | 不引入新类/新注入机制,在现有描述中增强 |
| DRY不重复 | ✅ | `build_tool_descriptions`已是统一入口 |

**第3轮: 修复确认**
- 🏆 已执行方案: 在 `build_tool_descriptions()` 中追加参数类型(type)、必填标记(required)、描述(description)
- commit: `90c30e5a refactor: 删除prompt层死代码+Prompt优化`
- 验证: 编译通过 + 测试通过

---

### 7.4 ❌ _TOOL_REMINDER 注入到 conversation_history 而非 prepare_messages

**文件**: `react_cycle.py:100-102`

```python
if parsed_type == "chunk" and not _has_tool_call(agent):
    agent.message_builder.conversation_history.append(
        {"role": "system", "content": _TOOL_REMINDER}
    )
```

**问题**: `_TOOL_REMINDER` 直接被追加到 `conversation_history`，但它是"当前轮"的临时提示，不应该成为永久历史。如果后续 LLM 调用正确处理了工具调用，这条提醒消息仍然存在于历史中，可能影响后续轮次的判断。

**更合理的做法**: 在 `_call_llm()` 的 `messages` 列表中动态注入（像已执行工具摘要一样），而不是永久写入 `conversation_history`。

**建议**: 改由 `_call_llm()` 在获取 `messages` 后判断是否需要注入 tool_reminder，而非在 `conversation_history` 中永久存储。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — react_cycle.py:100-102 仍用 `conversation_history.append()` 永久写入
- 每次纯文本回复都会追加一条 system role 的 `_TOOL_REMINDER`, 后续所有 LLM 调用都包含此消息
- 如果 LLM 连续3轮返回纯文本, history 中会有3条相同的 tool reminder, 浪费上下文窗口

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| **SLAP同一抽象层** | ❌ 违反 | `_process_single_step` 职责是"解析+调度",却做了"管理 conversation_history"的事 |
| YAGNI不过度设计 | ⚠️ 边界 | 永久写入在实践中不影响正确性(LLM能忽略旧system消息),但浪费tokens |
| KISS保持简单 | ⚠️ 边界 | 当前设计简单但不符合SLAP;修正会增加一点复杂度 |
| SRP单一职责 | ⚠️ 边界 | 消息注入应由 message_builder 或 _call_llm 负责 |

**第3轮: 最优方案**

方案A(推荐🏆): **标志位+动态注入** — 最小改动,最大SLAP提升
1. react_cycle.py line 100: `conversation_history.append(...)` → `agent._tool_reminder_needed = True`
2. _call_llm() 中: 检查标志,动态注入(像 _build_executed_tool_summary 一样)

```python
# react_cycle.py 改动
# 改前:
agent.message_builder.conversation_history.append(...)
# 改后:
agent._tool_reminder_needed = True
```

```python
# universal_agent.py _call_llm() 追加(在 openai_tools 构建后)
tool_reminder = _TOOL_REMINDER  # 从react_cycle导入
if getattr(self, '_tool_reminder_needed', False):
    messages.append({"role": "system", "content": tool_reminder})
    self._tool_reminder_needed = False
```

方案B(备选): 将 `_TOOL_REMINDER` 常量移入 `message_builder.py`, 通过 `message_builder.add_tool_reminder()` 追加到 `temp_history` — 但 temp_history 生命周期管理复杂, 不推荐。

---

### 7.5 ❌ file_prompts.py 中互斥参数和 text 规则信息过多但结构不佳

**文件**: `file_prompts.py:80-93`

**问题**: 
- P17互斥参数规则（5个工具的互斥说明）散落在 `get_system_prompt()` 底部，格式为纯文本，没有层次结构
- write_text_file text规则虽然重要，但放在 System Prompt 底部，LLM 容易忽略
- 不同的文件操作提示混在同一个纯文本块中

**建议**: 
- 将互斥参数规则移到 `TOOL_CALL_RULES` 或新建一个独立章节
- 使用结构化格式（如 Markdown 表格或列表）而不是纯文本段落

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — file_prompts.py:80-93 的 P17 互斥规则和 text 规则仍然是纯文本段落
- 原问题描述准确: 信息重要但结构不佳

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| SRP单一职责 | ✅ | 规则内容放在 get_system_prompt() 末尾,职责正确 |
| KISS保持简单 | ⚠️ 边界 | 纯文本确实简单,但LLM更容易忽略.结构化为列表更好 |
| YAGNI不过度设计 | ⚠️ 边界 | 纯文本能用但可优化 |
| P3-低优先级 | ✅ | 不影响功能正确性,属于可读性优化 |

**第3轮: 最优方案**

方案A(推荐🏆): **保持原位,改为列表格式** — 最小改动
```python
# file_prompts.py get_system_prompt() 末尾
"""【互斥参数规则 - 同一工具内禁止同时使用】:
- read_file: file_paths 单路径=单文件,多路径=批量
- edit_file: old_string 与 edits 互斥
- rename_file: path 与 directory 互斥
- archive_tool: compress→source+destination; extract→source
- file_operation: move/copy→destination; delete→无需destination

【write_text_file text规则】:
- text 参数必须传实际文件内容(代码/文本/正文)
- ❌ 禁止传入思考/计划/状态确认
- ✅ text="第一章:觉醒\n\n林凡是一名普通的大学生..." """
```

方案B: 将P17互斥规则移入 `TOOL_CALL_RULES` 基类常量末尾 — 但TOOL_CALL_RULES是通用规则,文件特有规则不应该放在基类。违反SRP。不推荐。

---

### 7.6 ❌ System Prompts 中 _build_examples() 示例类型混乱

**文件**: `system_prompts.py:49-61`

```python
_EXAMPLE_TEMPLATES = [
    {"tool_name": "get_weather", ...},     # 系统分类没有 get_weather 工具！
    {"tool_name": "finish", ...},
    {"tool_name": "search_files", ...},    # 搜索文件是 file 分类的工具
    {"tool_name": "read_file", ...},       # 读取文件是 file 分类的工具
    {"tool_name": "execute_shell_command", ...},  # shell 命令
    {"tool_name": "finish", ...},
]
```

**问题**: 
- `get_weather` 不是 `FUND_RUNTIME` 分类中的工具，会让 LLM 产生幻觉
- `search_files`, `read_file`, `execute_shell_command` 都不属于 `FUND_RUNTIME`
- 这些示例对 System Prompts 的 Agent 是误导性的

**建议**: 示例必须使用当前分类的工具，不能混入其他分类的工具。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ✅ 已修复 — `_build_examples()` 中的6个示例现在全部使用 FUND_RUNTIME 的真实注册工具
- 工具名对照:
  | 旧(错误) | 新(正确) | FUND_RUNTIME已注册 |
  |----------|---------|:------------------:|
  | get_weather | get_time | ✅ |
  | search_files | get_system_info | ✅ |
  | read_file | list_processes | ✅ |
  | execute_shell_command | query_calendar | ✅ |

**第2轮: 10大原则验证**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| KISS保持简单 | ✅ | 只有字符串替换,无逻辑变更 |
| 禁止backward compatibility | ✅ | 修复错误行为,不是兼容问题 |

**第3轮: 修复确认**
- 🏆 已执行方案: 修改 `_EXAMPLE_TEMPLATES` 中的6个示例,全部使用 FUND_RUNTIME 真实已注册工具
- commit: `90c30e5a refactor: 删除prompt层死代码+Prompt优化`
- 验证: 编译通过 + 测试通过

---

### 7.7 ❌ System Prompt 中 candidates_hint 和 cross_tool_hint 使用中文术语

**问题**: 
```python
# candidates_hint:
"【候选意图】用户任务可能属于以下分类: 文件操作(file)。如当前工具无法完成,可尝试其他分类的工具。"

# cross_tool_hint:
"【跨分类工具】当前已加载多分类工具: 文件操作, 基础运行时。可跨分类调用工具完成任务。"
```

**影响**: 英文的 System Prompt 中混入中文段落，可能影响非中文 LLM 的理解一致性。但考虑到 LLM 最终需要中文回复，倒不算严重问题。

**建议**: 保持现状或统一为英文（取决于 LLM 的偏好语言）。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — `_build_candidates_hint()` 和 `_build_cross_tool_hint()` 仍是全中文段落
- 影响: System Prompt 以中文为主(角色定义+规则都是中文),这两段中文与整体一致,实际影响为P3-低

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| YAGNI不过度设计 | ✅ | 整体Prompt已在用中文,这两段中文不影响一致性 |
| KISS保持简单 | ✅ | 当前状态就是最简单的 |

**第3轮: 最优方案**
- 🏆 **建议: 保持现状** — System Prompt 整体语言是中文,这两段中文与之一致
- 如果未来前端界面语言切换为英文,再统一调整

---

### 7.8 ❌ MessageBuilder 中 temp_history 的状态一致性风险

**文件**: `message_builder.py:110-114`

```python
def flush_temp_to_history(self, chunk_buffer: str) -> None:
    self.temp_history.clear()
    if chunk_buffer:
        self.add_assistant(chunk_buffer)
```

**问题**: 当 `temp_history` 中有数据时，`prepare_messages_for_llm()` 将其追加到 `messages` 末尾（第130行）。但如果 `flush_temp_to_history()` 被调用后（`temp_history` 清空），而新数据还未生成，那么下次 `prepare_messages_for_llm()` 返回的 messages 就不包含 `temp_history` 中的内容，导致历史断裂。

**影响**: 目前看起来这个函数只在合适的时机被调用，但逻辑脆弱，容易出错。

**建议**: 增加防御性检查，确保 `flush_temp_to_history()` 的调用时间点是安全的。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — `prepare_messages_for_llm()` 存在时序问题: `_cap_temp_history()` 在构建 `messages` 之后修改 `self.temp_history`
- ```python
  def prepare_messages_for_llm(self):       # ← message_builder.py:120
      messages = list(self.conversation_history)
      if self.temp_history:
          messages = messages + list(self.temp_history)  # ← 此时messages含完整temp_history
      self._cap_temp_history()              # ← 但self.temp_history被截断,下轮丢失数据
      return messages
  ```
- `flush_temp_to_history()` 本身逻辑正确(temp_history清空后内容已入conversation_history)

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| SLAP同一抽象层 | ⚠️ 轻微违规 | `prepare_messages_for_llm` 同时做"消息组装"和"容量维护" |
| KISS保持简单 | ⚠️ 轻微违规 | `_cap_temp_history()` 在后操作容易遗漏 |

**第3轮: 最优方案**

方案A(推荐🏆): **调换执行顺序** — 1行改动,在构建messages前先截断
```python
# message_builder.py:120-133
def prepare_messages_for_llm(self):
    self._cap_temp_history()                # ← 先截断
    messages = list(self.conversation_history)
    if self.temp_history:
        messages = messages + list(self.temp_history)
    return messages
```

方案B: 删除 `_cap_temp_history()` 调用,改成在 `add_observation` 或 `flush_temp_to_history` 中维护 — 破坏已有模式,不推荐。

---

### 7.9 ❌ trim_history() FC配对裁剪可能删除有效历史

**文件**: `message_builder.py:233-266`

**问题**: `_trim_fc_pairs` 对 `assistant.tool_calls ↔ tool` 配对进行检查，不匹配就双方都删除。但如果某条 `assistant` 消息在历史裁剪中被删除了（因为它在保留的最后10条之外），对应的 `tool` 消息就失去了配对，也会被删除。这可能导致 observation 历史的丢失。

**建议**: 在 `_rebuild_and_validate` 中确保重组后的 history 长度够长，或对 FC 配对消息有特殊的保留优先级。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — `_trim_fc_pairs` 仍会因 `_trim_to_budget` 提前删除assistant消息导致配对断裂
- 风险等级: P3-低,触发条件是"observation超过budget+FC配对恰好位于截断边界"
- 当前 `_rebuild_and_validate` 有兜底(history>10时取首2+尾8),但兜底也非FC安全

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| YAGNI不过度设计 | ⚠️ 边界 | 实际触发概率低,但一旦触发会丢掉有效observation |
| KISS保持简单 | ✅ | 当前逻辑不算复杂 |

**第3轮: 最优方案**

方案A(推荐🏆): **在 `_trim_to_budget` 中对FC配对的tool消息优先保留**
```python
# message_builder.py _trim_to_budget() 中,在 pop(0) 截断前:
def _trim_to_budget(self, obs_list, assistant_msgs, budget):
    obs_list = self._dedup_by_fingerprint(obs_list)
    assistant_msgs = assistant_msgs[-10:]
    obs_list = obs_list[-30:]
    while obs_list and self._total_chars(obs_list) > budget:
        # 🏆 优先移除非FC(tool)消息;如果全部是FC消息,从最旧开始删
        non_fc = [i for i, m in enumerate(obs_list) if m.get("role") != "tool"]
        if non_fc:
            idx = non_fc[0]
        else:
            idx = 0
        obs_list.pop(idx)
    return obs_list
```

方案B: 在 `_rebuild_and_validate` 的兜底中保护FC配对 — 但兜底本身是最后防线,不适用。

---

### 7.10 ❌ BaseAIService._build_messages() 与 message_utils.build_llm_messages() 重复

**文件**: `llm_core.py:236-246` vs `message_utils.py:15-28`

```python
# llm_core.py
def _build_messages(self, message, history=None):
    messages = []
    if history:
        for msg in history:
            messages.append(msg if isinstance(msg, dict) else {"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})
    return messages

# message_utils.py
def build_llm_messages(message, history=None):
    if not message and history:
        return list(history)
    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})
    return messages
```

**问题**: 两个函数功能高度重叠，违反了 DRY 原则。`message_utils.py` 的注释说"替代llm_core._build_messages()"，但并没有真的替代——两个函数都存在。

**影响**: 未来改了一个忘了改另一个。

**建议**: 删除 `llm_core.py` 中的 `_build_messages()`，统一使用 `message_utils.build_llm_messages()`。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — `llm_core.py:236` 的 `_build_messages()` 和 `message_utils.py:15` 的 `build_llm_messages()` 同时存在
- `build_llm_messages` 的注释说"替代llm_core._build_messages()"但从未被调用
- `_build_messages` 仍被 `BaseAIService.chat()` 调用,该方法是公共API(SSE服务层用)
- 两函数功能: `[history..., {"role":"user", "content": message}]`, 几乎相同

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| **DRY不重复** | ❌ 违反 | 完全相同的消息构建逻辑写了两次 |
| KISS保持简单 | ⚠️ 违反 | 两个函数做同一件事,维护者困惑 |
| SRP单一职责 | ✅ | 去掉重复后各自职责清晰 |

**第3轮: 最优方案**

方案A(推荐🏆): **删除 `llm_core._build_messages()`, `chat()` 内联调用 `message_utils.build_llm_messages()`**
```python
# llm_core.py 改动
# 改前:
def _build_messages(self, message, history=None):
    ...  # 16行代码
async def chat(self, message, history=None):
    messages = self._build_messages(message, history)
    ...

# 改后:
async def chat(self, message, history=None):
    from app.services.agent.agent_utils.message_utils import build_llm_messages
    messages = build_llm_messages(message, history)
    ...

# 然后删除 _build_messages 方法
```

**注意**: `_build_messages` 额外支持 `msg.role`/`msg.content` 对象属性访问,而 `build_llm_messages` 只接受 dict。chat()的调用方 `run_sse_stream.py` 传的是 dict,所以兼容。

---

### 7.11 ❌ BaseAIService.callback 参数传递冗余

**问题**: `BaseAIService` 的 `request()` 和 `request_stream()` 方法都接收 `mode`, `tools`, `tool_choice` 三个参数，这些参数被层层透传（`universal_agent → BaseAIService → LLMClient`）。M 但这些参数在 `LLMClient._build_request_body()` 中只对 `mode=="tools"` 时有意义，对 `mode=="text"` 时 `tools` 和 `tool_choice` 被忽略。

**影响**: 参数透传层数多，修改时需要改多个文件。

**建议**: 考虑用 `LLMRequestConfig` 数据类封装这些参数，减少透传参数个数。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — mode/tools/tool_choice 仍逐层透传(`_call_llm → _call_llm_fc_stream → client_sdk._build_request_body`)
- 透传层级: universal_agent → BaseAIService.request_stream → LLMClient.request_stream → _build_request_body
- 影响: P3-低,实际上不影响功能正确性

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| **YAGNI不过度设计** | ✅ | 引入数据类会增加复杂度,当前透传可用 |
| **KISS保持简单** | ✅ | 保持独立参数是Python惯用做法 |
| SLAP同一抽象层 | ⚠️ 轻微 | 透传多但抽象层一致 |

**第3轮: 最优方案**
- 🏆 **建议: 保持现状** — `mode`/`tools`/`tool_choice` 3个参数透传不算多,引入数据类会增加复杂性却不带来实质收益
- 当参数增加到5个以上时才考虑封装

---

### 7.12 ❌ observation_formatter 中 format_llm_observation 与 message_builder._normalize_observation_prefix 双重前缀

**文件**: `observation_formatter.py:187-199` and `message_builder.py:205-217`

**问题**: 
- `format_llm_observation()` 返回的内容以 `"Observation: success - ..."` 开头
- `_normalize_observation_prefix()` 将其转换为 `"[Observation] success - ..."`

这一过程虽然没有错（`_normalize_observation_prefix` 处理了所有前缀变体），但两个模块都在处理"Observation 前缀"，职责边界不清。

**建议**: 统一前缀处理职责——`observation_formatter` 只负责数据内容格式化，前缀处理完全由 `message_builder` 负责（当前现状 OK，但需要文档说明）。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — 职责边界模糊但实际运行正确
- 数据流: `observation_formatter.format_llm_observation()` → `"Observation: success - ..."` → `message_builder._normalize_observation_prefix()` → `"[Observation] success - ..."`
- `_normalize_observation_prefix()` 已经有防双重前缀逻辑(检查已在"[Observation]"开头的跳过)

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| SRP单一职责 | ⚠️ 边界 | 两个模块都参与前缀处理,但各自功能清晰 |
| KISS保持简单 | ✅ | 当前现状最简单,加一层抽象反而复杂 |
| YAGNI不过度设计 | ✅ | 不是bug,不需要修改 |

**第3轮: 最优方案**
- 🏆 **建议: 保持现状 + 文档说明** — 当前虽然职责边界模糊,但 `_normalize_observation_prefix` 已正确兜底
- 只需要在 `observation_formatter.py` 和 `message_builder.py` 添加文档注释说明前缀处理的分工即可

---

### 7.13 ❌ tool 注册描述中 "When to use" 中文混用

**文件**: `base_prompt_template.py:244-245`

```python
lines.append(f"   - When to use: 当需要{desc_first}时")
```

**问题**: "When to use:" 是英文，"当需要...时" 是中文，中英混用。System Prompt 的整体语言应该是统一的中文（因为回复要求用中文）。

**建议**: 改为统一的 `"使用场景: 当需要{desc_first}时"`。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — `base_prompt_template.py:239` 仍是 `f"   - When to use: 当需要{desc_first}时"`
- 中英混用: "When to use:" 是英文, "当需要...时" 是中文
- 影响: P3-低,轻微不一致

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| KISS保持简单 | ✅ | 字符串替换 |
| YAGNI不过度设计 | ✅ | 最小改动 |

**第3轮: 最优方案**
方案A(推荐🏆): **统一为中文**
```python
# base_prompt_template.py:239
# 改前:
lines.append(f"   - When to use: 当需要{desc_first}时")
# 改后:
lines.append(f"   - 使用场景: 当需要{desc_first}时")
```

---

### 7.14 ❌ System Prompt 中 OUTPUT_FORMAT 强制 JSON 格式但 FC 模式下不需要

**问题**: `OUTPUT_FORMAT` 常量强制 LLM 使用 JSON 格式输出（`{"thought":..., "tool_name":..., ...}`），但 FC 模式（`mode="tools"`）下 LLM 使用 OpenAI 的 function calling 协议输出 `tool_calls`，与 JSON 格式不同。

**影响**: 当使用支持 FC 的模型时，System Prompt 中要求 JSON 的输出格式可能造成 LLM 的困惑——它应该输出 `tool_calls` 还是 JSON？

**建议**: 在 `mode="tools"` 时，System Prompt 的 `OUTPUT_FORMAT` 应调整为 FC 模式的说明，而非 JSON 格式的说明。或者统一仅使用 Text 模式（完全去掉 FC 模式）。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ✅ 已修复 — `build_full_system_prompt(strategy)` 在 `strategy="tools"` 时跳过 `OUTPUT_FORMAT`
- 实际效果: FC模式下System Prompt减少约200+ token(删除整个OUTPUT_FORMAT段落)
- 采用"跳过"而非"替换为FC说明"方案,因为FC协议格式由API的tool_calls定义,不需要prompt描述

**第2轮: 10大原则验证**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| OCP开闭原则 | ✅ | `build_full_system_prompt` 加了参数但不改原有行为 |
| YAGNI不过度设计 | ✅ | 不引入FC专用OUTPUT_FORMAT,跳过即可 |
| KISS保持简单 | ✅ | `if strategy != "tools": parts.append(...)` |

**第3轮: 修复确认**
- 🏆 已执行方案: `build_full_system_prompt(strategy)` + universal_agent 传 `strategy="tools"`
- commit: `90c30e5a refactor` + `d90481c1a fix`
- 验证: 编译通过 + 测试通过

---

### 7.15 ❌ BaseAIService 单例模式潜在问题

**文件**: `factory/get_service.py`

**问题**: `BaseAIService` 是全局单例，但 `llm_core.py:46-47` 有可变状态:

```python
self._cancelled = False
self._current_response: Optional[httpx.Response] = None
self.task_id: Optional[str] = None
```

单例共享 `_cancelled` 和 `task_id`，如果在多会话并发场景下（即使是同一个线程处理不同请求），A 会话的 `cancel()` 可能意外取消 B 会话的请求。

**影响**: 竞态条件，误取消。

**建议**: 已通过 `task_registry` 的 `check_cancelled(task_id)` 做了一定缓解，但 `_cancelled` 和 `_current_response` 的危险依然存在。建议每个请求使用独立的 `BaseAIService` 实例，或确保 `set_task_id`/`cancel` 的调用时序完全正确。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ✅ 已缓解 — `get_service.py` 已实现 `threading.Lock` + double-checked locking
- `reset_instance()` / `set_instance()` / `cleanup_old_instance()` 等公开API完整
- 但 `BaseAIService` 内部 `_cancelled` 和 `_current_response` 仍是实例可变状态
- 风险等级: P1→P2,锁降低了并发风险但未完全消除

**第2轮: 10大原则验证**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| KISS保持简单 | ⚠️ 边界 | 单例+双重检查锁是标准模式,复杂但必要 |
| YAGNI不过度设计 | ✅ | 多会话并发的场景确实需要线程安全 |
| 禁止backward compatibility | ✅ | 保持现有API不变 |

**第3轮: 最优方案**
- 🏆 **建议: 保持当前实现** — `threading.Lock` + task_registry.check_cancelled(task_id)的组合已充分缓解
- 如果需要完全消除风险,需架构级变更(BaseAIService改为无状态工厂+每个请求独立实例) — 超出本次优化范围

---

### 7.16 ❌ react_cycle 中 `_process_single_step` 的 `chunk_buffer` 传递

**问题**: `_process_single_step()` 接收 `chunk_buffer` 参数，但 `chunk_buffer` 是可变对象，由 `run_react_cycle` 创建并在循环中共享。`chunk_handler.py` 中的 `handle_chunk_buffer_promotion()` 修改了 `chunk_buffer` 的内部状态。这种隐式状态修改增加了理解难度。

**影响**: 代码可读性降低。

**建议**: `chunk_buffer` 的操作应该封装在 `ChunkBuffer` 类的方法中，外部通过返回新状态而非修改内部状态的方式来使用。

---

### 🔎 小健3轮复核(2026-06-11 05:18:28)

**第1轮: 问题真实性验证**
- ❌ 未修复 — `chunk_buffer` 仍是从 `initialize_run_state()` 返回的可变对象,在循环中共享修改
- `chunk_handler.py` 的 `handle_chunk_buffer_promotion()` 直接修改 chunk_buffer 内部状态
- 影响: P3-低,可读性问题而非功能bug

**第2轮: 10大原则评估**
| 原则 | 符合 | 说明 |
|------|:----:|------|
| SLAP同一抽象层 | ⚠️ 违反 | handler修改chunk_buffer状态,隐式耦合 |
| KISS保持简单 | ⚠️ 边界 | 可变对象共享是简单但危险的模式 |
| YAGNI不过度设计 | ⚠️ 边界 | 修改为不可变模式增加复杂度 |

**第3轮: 最优方案**
- 🏆 **建议: 保持现状** — 当前 chunk_buffer 可变对象模式是Python常见模式(类似list/dict作为默认参数),虽然不完美但实际风险低
- 修改为不可变模式(每次返回新状态)需要重构 `handle_chunk_buffer_promotion` 和所有调用方,收益不足以 justify 成本
- 如未来需要,可以在重构 chunk_buffer 时统一改为不可变 FrozenChunkBuffer 模式

---

## 八、重点关注问题总结

### 8.1 严重程度分类

| 级别 | 问题 | 状态 | 影响 |
|------|------|:----:|------|
| **P1-高** | 7.1 get_observation_prompt() 死代码 | ✅ 已修复 | 维护陷阱 |
| **P1-高** | 7.2 get_parameter_reminder() 死代码 | ✅ 已修复 | 维护陷阱，误导新开发者 |
| **P1-高** | 7.6 SystemPrompts 示例使用不存在工具 | ✅ 已修复 | 导致 LLM 幻觉 |
| **P1-高** | 7.15 BaseAIService 单例可变状态 | ⚠️ 已缓解(P2) | 并发取消竞态 |
| **P2-中** | 7.3 Text模式缺少参数Schema | ✅ 已修复 | LLM 可能填错参数 |
| **P2-中** | 7.4 TOOL_REMINDER 永久写入历史 | ❌ 待修 | 历史污染风险 |
| **P2-中** | 7.10 _build_messages 重复定义 | ❌ 待修 | DRY违反 |
| **P2-中** | 7.14 OUTPUT_FORMAT与FC模式冲突 | ✅ 已修复 | 模型可能困惑 |
| **P3-低** | 7.5 互斥参数结构不佳 | ❌ 待修 | 可读性差 |
| **P3-低** | 7.7 中英文混用 | ❌ 保持现状 | 轻微不一致 |
| **P3-低** | 7.8 temp_history 状态一致性 | ❌ 待修 | 边界脆弱 |
| **P3-低** | 7.9 FC配对可能丢失历史 | ❌ 待修 | 边界条件 |
| **P3-低** | 7.11 参数透传冗余 | ❌ 保持现状 | 代码冗余 |
| **P3-低** | 7.13 中英混用 | ❌ 待修 | 轻微不一致 |
| **P3-低** | 7.16 chunk_buffer 可变传递 | ❌ 保持现状 | 可读性降低 |

### 8.2 修复状态总结

| 状态 | 问题数 | 问题编号 |
|:----:|:------:|---------|
| ✅ 已修复 | 5 | 7.1, 7.2, 7.3, 7.6, 7.14 |
| ❌ 待修复 | 5 | 7.4, 7.5, 7.8, 7.9, 7.10, 7.13 |
| ⚠️ 已缓解/保持现状 | 5 | 7.7, 7.11, 7.12, 7.15, 7.16 |

### 8.3 待修复问题优先级

1. **P2-中** 7.4: TOOL_REMINDER 改为标志位动态注入(SLAP违反复核)
2. **P2-中** 7.10: 删除 llm_core._build_messages(),统一用 message_utils.build_llm_messages()(DRY违反)
3. **P3-低** 7.8: 调换 _cap_temp_history() 执行顺序(1行修复)
4. **P3-低** 7.13: "When to use" 统一为 "使用场景"(1行修复)
5. **P3-低** 7.5: file_prompts互斥参数改为结构化列表
6. **P3-低** 7.9: _trim_to_budget 优先保留FC配对消息

---

## 九、数据流最终形态（发给 LLM 的完整消息）

### 第0轮 messages 结构

```json
[
  {
    "role": "system",
    "content": "【当前系统】\nWindows\n\n【路径格式】\n...\n\n# File Operation Tools\n\n  ...\n\n【Response Format - 必须遵守】\n...\n\n【Tool Call Rules - 极其重要】\n...\n\n【避免重复规则】\n...\n"
  },
  {
    "role": "user",
    "content": "Task: 读取桌面上的config.json文件\n\nCurrent time: 2026-06-10 15:00:00\n\n请完成此文件管理任务,按以下步骤:\n1. 分析需要做什么操作\n2. 使用合适的工具完成任务\n3. 用中文总结结果\n"
  }
]
```

### 第1轮 messages 结构（第1次工具调用后）

```json
[
  {"role": "system", "content": "...（完整System Prompt）..."},
  {"role": "user", "content": "Task: 读取桌面上的config.json文件..."},
  {"role": "assistant", "content": "{\"thought\":\"用户要读取文件\",\"tool_name\":\"read_file\",\"tool_params\":{\"file_paths\":[\"C:/Users/xxx/Desktop/config.json\"]}}"},
  {"role": "user", "content": "[Tool Result]\nObservation: success - 文件读取成功\n数据: {\"content\": \"{\\\"key\\\": \\\"value\\\"}\"}"},
  {"role": "system", "content": "【已执行工具(勿重复)】read_file→success|文件:C:/Users/xxx/Desktop/config.json\n注意:上述工具已成功执行,结果已在Observation中,禁止再次调用!"}
]
```

### 第N轮 messages 结构

```json
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "Task: ..."},
  {"role": "assistant", "content": "..."},
  {"role": "user", "content": "[Tool Result]\n..."},    // 或被替换为 FC 协议
  {"role": "assistant", "content": "..."},                // 后续轮次
  {"role": "user", "content": "[Tool Result]\n..."},
  // ... 以此类推
  // 最后注入:
  {"role": "system", "content": "【已执行工具(勿重复)】..."}
]
```

---

## 十、复查记录

| 复查次数 | 复查时间 | 复查人 | 发现问题数 | 说明 |
|---------|---------|--------|-----------|------|
| 第1遍 | 2026-06-10 15:17 | 小沈 | 原始分析 | |
| 第2遍 | 2026-06-10 15:18 | 小沈 | 0 | 章节结构验证 |
| 第3遍 | 2026-06-10 15:19 | 小沈 | 0 | 数据流追踪验证 |
| 第4遍 | 2026-06-10 15:20 | 小沈 | 0 | 代码引用检查 |
| 第5遍 | 2026-06-10 15:21 | 小沈 | 0 | 全文通读校验 |
| **第6遍** | **2026-06-11 05:18** | **小健** | **16** | **全问题逐题3轮复核+X原则评估+最优方案** |

---

**文档完成时间**: 2026-06-10 15:21:00
**版本v1.1更新时间**: 2026-06-11 05:18:28
**版本v1.1更新人**: 小健
**编写人**: 小沈
