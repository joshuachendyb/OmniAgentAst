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
| v1.2 | 2026-06-11 (代码同步) | 小欧 | 逐节核对当前代码,修复9处差异 |

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
│    │  ├─ _get_system_prompt() → build_full_system_prompt(strategy)   │
│    │  │   = get_system_prompt() + OUTPUT_FORMAT(FC跳过)              │
│    │  │   + TOOL_CALL_RULES + safety_reminder + rollback_instructions│
│    │  │   + AVOID_REPEAT_RULES + candidates_hint + cross_tool_hint   │
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

**文件**: `universal_agent.py:69-82` `_get_system_prompt()`

```python
def _get_system_prompt(self) -> str:
    if not hasattr(self, 'prompts') or not self.prompts:   # ← 守卫
        return "System: 通用助手"
    
    strategy = "tools" if self.tool_category is not None else None  # ← FC模式传strategy
    base_prompt = self.prompts.build_full_system_prompt(strategy=strategy)
    candidates_hint = self._build_candidates_hint()         # ← 候选意图提示
    cross_tool_hint = self._build_cross_tool_hint()         # ← 跨分类工具提示
    parts = [base_prompt]
    if candidates_hint: parts.append(candidates_hint)
    if cross_tool_hint: parts.append(cross_tool_hint)
    return "\n\n".join(parts)
```

### 3.2 基类组装顺序

**文件**: `base_prompt_template.py:176-212` `build_full_system_prompt(strategy: Optional[str] = None)`

组装顺序如下（FC模式跳过②，由API Schema约束格式）：

| 顺序 | 段名 | 来源 | 是否分类特有 | 说明 |
|------|------|------|-------------|------|
| ① | `get_system_prompt()` | 子类实现 | ✅ 是 | 分类Agent角色定义 + 工具描述 + Examples |
| ② | `OUTPUT_FORMAT` | 基类常量 | ❌ 否 | JSON输出格式（FC模式跳过） |
| ③ | `TOOL_CALL_RULES` | 基类常量 | ❌ 否 | 工具调用规则（含SAFETY WARNING） |
| ④ | `get_safety_reminder()` | 子类覆盖 | ✅ 是 | 安全提醒（默认空） |
| ⑤ | `get_rollback_instructions()` | 基类方法 | ❌ 否 | 回滚说明（中英混用） |
| ⑥ | `AVOID_REPEAT_RULES`（类常量） | 基类常量 | ❌ 否 | 避免重复规则 |

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

【Tool Call Rules】:
- 确认用户意图后立即调用工具...

【避免重复规则】
- 同一命令/URL成功后不要重复执行...

【候选意图】用户任务可能属于以下分类: ...
```

**整个 System Prompt 的段数**: 7或6段（FC模式跳过OUTPUT_FORMAT）。组装：分类特有 + OUTPUT_FORMAT(FC跳过) + TOOL_CALL_RULES(含SAFETY WARNING) + safety + rollback + AVOID_REPEAT_RULES + candidates/cross_tool

**注**: `SAFETY WARNING`已于2026-06-11合并到TOOL_CALL_RULES；`AVOID_REPEAT_RULES`已提取为类常量(2026-06-11)。

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
| `system` | _call_llm() 标志位注入 | `BasePrompts.TOOL_REMINDER` | 无工具调用时设标志,由_call_llm()动态注入(不写永久历史) |
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

**文件**: `universal_agent.py:128-151`

```python
async def _call_llm(self):
    """调用LLM — FC优先,降级text流式 — 小沈 2026-06-11"""
    self.llm_call_count += 1
    self.message_builder.trim_history()
    messages = self.message_builder.prepare_messages_for_llm()
    
    executed_summary = self._build_executed_tool_summary()
    if executed_summary:
        messages.append({"role": "system", "content": executed_summary})
    
    # 工具提醒惰性注入:不永久写入conversation_history
    if getattr(self, '_tool_reminder_needed', False):
        from app.services.prompts.base_prompt_template import BasePrompts
        messages.append({"role": "system", "content": BasePrompts.TOOL_REMINDER})
        self._tool_reminder_needed = False
    
    openai_tools = self._get_openai_tools()
    if not openai_tools:
        logger.error(f"[call_llm] 无可用工具, category={self.tool_category}")
    
    # FC优先:所有场景都过FC流式(无工具也由API处理)
    async for item in self._call_llm_fc_stream(messages, openai_tools):
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
1. observation 去重（基于MD5指纹,FC协议消息不参与去重）
2. assistant分离: tool_call_msgs保留最新10条, text_msgs保留最新5条(优先保留FC配对)
3. observation分离: tool-role(FC)保留最新15条, text-role先裁剪(优先FC配对)
4. 从最旧 observation 开始截断直到 <= MAX_CONTEXT_CHARS * 0.7
5. FC配对完整性修复（assistant.tool_calls ↔ tool 配对）

---

## 六、LLM 调用链路

### 6.1 调用栈

```
universal_agent._call_llm()   ← FC优先: 所有场景过FC流式
  └─ _call_llm_fc_stream()    ← 异常/纯文本降级 _convert + _call_llm_text_stream
      ├─ llm_client.request_stream(messages, mode="tools", tools=...)
      │   └─ BaseAIService.request_stream()
      │       └─ LLMClient.request_stream()
      │           └─ POST /chat/completions {model, messages, tools, tool_choice}
      │                                     ← FC降级3路径:
      ├→ 异常降级: _convert_fc_messages_to_text() → _call_llm_text_stream()
      ├→ stream_error降级: _convert_fc_messages_to_text() → _call_llm_text_stream()
      └→ 纯文本兜底: full_content.strip() → _convert_fc_messages_to_text() → _call_llm_text_stream()
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

| 维度 | FC模式 | Text模式(当前降级用) |
|------|--------|---------------------|
| **请求体** | `{messages, tools, tool_choice:"auto"}` | `{messages}` |
| **LLM响应** | delta.tool_calls 流 | delta.content 流 |
| **解析** | SSE流聚合tool_calls → JSON | 纯文本JSON解析 |
| **降级** | 流失败/纯文本 → _convert_fc_messages_to_text() + _call_llm_text_stream() | 流失败 → _call_llm_text_nostream |

**注**: 自2026-06-11起,`_call_llm`改为FC-only(所有场景过FC流式)。旧有`_call_llm_text_stream`分支已移除,现在`_call_llm_text_stream`仅作为FC降级路径使用。降级前先调用`_convert_fc_messages_to_text()`将FC协议消息转为Text格式。

---



## 九、数据流最终形态（发给 LLM 的完整消息）

### 第0轮 messages 结构

> **注意**: 以下为Text模式(strategy=None)的完整结构。FC模式(strategy="tools")下，System Prompt中**不包含**`【Response Format - 必须遵守】`段（由API的tool_calls协议替代）。

```json
[
  {
    "role": "system",
    "content": "【当前系统】\nWindows\n\n【路径格式】\n...\n\n# File Operation Tools\n\n  1. read_file - 读取文件内容\n     - 使用场景: 当需要读取文件内容时\n     - 参数: file_paths(array)(必填):文件路径列表\n     - 返回: 操作结果\n  ...\n\n【Response Format - 必须遵守】\n...  ← FC模式下跳过此段\n\n【Tool Call Rules】\n...\n\n【避免重复规则】\n..."
  },
  {
    "role": "user",
    "content": "Task: 读取桌面上的config.json文件\n\nCurrent time: 2026-06-10 15:00:00\n\n请完成此文件管理任务,按以下步骤:\n1. 分析需要做什么操作\n2. 使用合适的工具完成任务\n3. 用中文总结结果\n"
  }
]
```

### 第1轮 messages 结构（第1次工具调用后）

> **注意**: `【已执行工具(勿重复)】`为动态注入（7.4修复后），仅当`_executed_tool_summary`非空时追加。`【系统提示·工具调用提醒】`为标志位动态注入，仅当LLM未调用工具时追加（不写永久历史）。

```json
[
  {"role": "system", "content": "...（完整System Prompt）..."},
  {"role": "user", "content": "Task: 读取桌面上的config.json文件..."},
  {"role": "assistant", "content": "{\"thought\":\"用户要读取文件\",\"tool_name\":\"read_file\",\"tool_params\":{\"file_paths\":[\"C:/Users/xxx/Desktop/config.json\"]}}"},
  {"role": "user", "content": "[Tool Result]\nObservation: success - 文件读取成功\n数据: {\"content\": \"{\\\"key\\\": \\\"value\\\"}\"}"},
  {"role": "system", "content": "【已执行工具(勿重复)】read_file→success|文件:C:/Users/xxx/Desktop/config.json\n注意:上述工具已成功执行,结果已在Observation中,禁止再次调用!"},
  {"role": "system", "content": "【系统提示·工具调用提醒】\n你刚才的回复没有调用任何工具...（仅当LLM未调用工具时动态注入，用后即清）"}
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
  // 动态注入（按需追加，非永久历史）:
  {"role": "system", "content": "【已执行工具(勿重复)】..."},  // _executed_tool_summary 非空时追加
  {"role": "system", "content": "【系统提示·工具调用提醒】..."}  // LLM未调用工具时追加，用后即清
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
| **第7遍** | **2026-06-11 代码同步** | **小欧** | **9** | **逐节核对代码,修复9处差异(guard/strategy/FC-only/TOOL_REMINDER/trim)** |

---

**文档完成时间**: 2026-06-10 15:21:00
**版本v1.2更新时间**: 2026-06-11 (代码同步校验)
**版本v1.2更新人**: 小欧
**更新内容**: 逐节核对代码，修复9处差异（_get_system_prompt guard+strategy, build_full_system_prompt strategy+AVOID_REPEAT_RULES, _call_llm FC-only+tool_reminder, trim_history FC配对保护, TOOL_CALL_RULES标题, 降级路径）
**编写人**: 小沈
