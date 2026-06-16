# LLM Prompt 与 Message 全系统分析报告

**创建时间**: 2026-06-10 15:17:04
**版本**: v2.2
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
| **v2.0** | **2026-06-12 (代码复核)** | **小欧** | **逐节复核本地代码，更新全部章节以匹配FC-only架构** |
| **v2.1** | **2026-06-12 12:22:05** | **小欧** | **FC-only精简化改造: TOOL_CALL_RULES合并AVOID_REPEAT_RULES; build_full_system_prompt从8段→4段; candidates_hint+cross_tool_hint移至_call_llm每轮注入** |
| **v2.2** | **2026-06-12 北京老陈** | **小欧** | **移除** AGENT_REGISTRY["file"] + FileOperationPrompts; CRSS返回FILE直接走system agent |

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
| **API入口** | `api/v1/chat/chat_stream_v2.py` |
| **SSE运行器** | `services/agent/core_agent/react_cycle.py`（内联调度） |
| **Agent工厂** | `agent_factory.py`, `agent_config.py` |
| **Agent核心** | `universal_agent.py`, `core_agent/base_agent.py`, `core_agent/agent_initializer.py` |
| **ReAct循环** | `core_agent/react_cycle.py`, `core_agent/initialize_run_state.py` |
| **Handler** | `core_agent/handlers/action_handler.py`, `answer_handler.py`, `chunk_handler.py`, `error_handler.py` |
| **Message管理** | `message_builder.py`, `agent_utils/message_utils.py`, `agent_utils/fc_message_types.py` |
| **Prompt基类** | `base_prompt_template.py` |
| **Prompt子类** | ~~`file/file_prompts.py`~~(已删), `system/system_prompts.py`, `network/network_prompts.py`, `desktop/desktop_prompts.py`, `document/document_prompts.py`, `meta/time_prompts.py` |
| **中间层** | `middle/system_adapter.py`, `middle/__init__.py` |
| **Observation** | `observation_formatter.py`, `agent_utils/message_utils.py` |
| **LLM响应解析** | `universal_agent.py`中`chunk.tool_calls`原生消费（parse_llm_response.py已于2026-06-11删除，2026-06-12去JSON roundtrip） |
| **LLM SDK** | `llm/client_sdk.py` |
| **Prompt日志** | `utils/prompt_logger.py` |
| **工具相关** | `constants.py`, `utils/time_utils.py` |
| **Steps类型** | `steps/action_step.py`, `chunk_step.py`, `thought_step.py`, `observation_step.py`, `final_step.py`, `error_step.py`, `incident_step.py`, `start_step.py`, `base.py` |
| **工具引擎** | `tool_retry_engine.py`, `core_agent/tool_manager.py` |

---

## 二、完整数据流（概览）

```
┌─────────────────────────────────────────────────────────────────────┐
│                   完整 Prompt/Message 数据流（FC-only）               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  用户输入 → API路由 → detect_intent() → intent_type + candidates     │
│    │                                                                 │
│    ▼ AgentFactory.create() → UniversalAgent                          │
│    │  └─ config.prompt_class = SystemPrompts (举例,File已删除)       │
│    │  └─ config.exclude_tool_details_from_prompt 控制是否跳过工具描述 │
│    │                                                                 │
│    ▼ agent._initialize_run_state()                                   │
│    │  ├─ _get_system_prompt() → build_full_system_prompt()           │
│    │  │   = _get_system_info() + _get_project_context()              │
│    │  │   + get_core_system_prompt()                                 │
│    │  │   + TOOL_CALL_RULES(safety合并)                              │
│    │  │   ※ FC-only: 4段,无OUTPUT_FORMAT（API Schema约束格式）      │
│    │  │   ※ ~~candidates_hint+cross_tool_hint~~ 已移除（FC协议已覆盖）│
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
│    │   ├─ agent._call_llm() → _call_llm_fc_stream（纯FC,无降级）     │
│    │   │  ├─ message_builder.trim_history()     ← FC-only裁剪        │
│    │   │  ├─ messages = prepare_messages_for_llm()                   │
│    │   │  ├─ ~~_build_executed_tool_summary()~~ 已移除               │
│    │   │  ├─ ~~_build_candidates_hint()~~       已移除               │
│    │   │  ├─ ~~_build_cross_tool_hint()~~       已移除               │
│    │   │  │  ※ 无TOOL_REMINDER（FC-only已移除）                     │
│    │   │  └─ llm_client.request_stream(messages, tools)             │
│    │   │     └─ LLMClient → POST /chat/completions {tools}          │
│    │   │                                                             │
│    │   ├─ _call_llm_fc_stream() tool_calls原生消费（无JSON roundtrip）│
│    │   │  → chunk.tool_calls存在？action(原生dict):answer             │
│    │   │                                                             │
│    │   └─ handler 注册式分派（_TYPE_HANDLERS）                       │
│    │      ├─ action_handler: → message_builder.add_observation()     │
│    │      │  （FC协议: assistant(tool_calls) + role:tool）           │
│    │      └─ answer_handler: agent.status = COMPLETED                │
│    │                                                                 │
│    └── 循环直到 status=COMPLETED/FAILED 或 max_steps 耗尽              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**关键更新（v2.0）**:
- `build_full_system_prompt()` 无 `strategy` 参数，纯FC-only
- System Prompt 组装改为 8 段（含 `_get_system_info()` + `_get_project_context()`）
- `OUTPUT_FORMAT`/`TOOL_REMINDER` 已删除
- `_call_llm()` 纯FC流式，无Text降级路径
- `parse_llm_response.py` 已删除，`_call_llm_fc_stream()` 消费 `chunk.tool_calls`
- Observation 使用FC协议（`role: assistant(tool_calls)` + `role: tool`）

**关键更新（v2.1）**:
- `TOOL_CALL_RULES` 合并 `AVOID_REPEAT_RULES`，移除FC冗余规则（#1/#3/#4）
- `build_full_system_prompt()` 从8段→4段：移除 `get_tool_details()`(可选)/`rollback_instructions`/`AVOID_REPEAT_RULES`，safety合并入规则段

**2026-06-12 北京老陈 精简**:
- `_build_executed_tool_summary()` / `_build_candidates_hint()` / `_build_cross_tool_hint()` **全部移除** — FC协议已覆盖，无需prompt hack

---

## 三、System Prompt 构建（逐段分析）

### 3.1 构建入口

**文件**: `universal_agent.py:69-72` `_get_system_prompt()`

```python
def _get_system_prompt(self) -> str:
    if not hasattr(self, 'prompts') or not self.prompts:
        return "System: 通用助手"
    return self.prompts.build_full_system_prompt()   # ← v2.1: 直接返回4段组装,无candidates/cross_tool
```

**注（v2.1→2026-06-12）**: `candidates_hint` 和 `cross_tool_hint` 曾在`_call_llm()`动态注入，后与 `_build_executed_tool_summary()` 一并移除。

### 3.2 基类组装顺序

**文件**: `base_prompt_template.py:189-228` `build_full_system_prompt(include_tool_details: bool = None)`

组装顺序如下（FC-only v2.1精简化版，从8段→4段）：

| 顺序 | 段名 | 来源 | 是否分类特有 | 说明 |
|------|------|------|-------------|------|
| ① | `_get_system_info()` | 基类方法 | ❌ 否 | 服务器OS/路径格式/环境信息 |
| ② | `_get_project_context()` | 基类方法 | ❌ 否 | 项目上下文（README.md），有则追加 |
| ③ | `get_core_system_prompt()` | 子类实现 | ✅ 是 | 分类Agent角色定义 + 业务规则 |
| ④ | `TOOL_CALL_RULES` | 基类常量 | ❌ 否 | 回答要求+停止条件+执行效率 |

**v2.1移除的段（FC-only精简化）**:
- `get_tool_details()` → 由FC Schema承载，不再Prompt中注入
- `get_rollback_instructions()` → LLM自然能从`role:tool`错误消息理解失败原因，无需额外指令
- `AVOID_REPEAT_RULES` → 合并入`TOOL_CALL_RULES`【执行效率】段
- `get_safety_reminder()` → **已移除**，后续由独立安全机制处理（2026-06-12 北京老陈）
- `candidates_hint` + `cross_tool_hint` → 移至`_call_llm()`每轮动态注入 → **后已全部移除**
- `_build_executed_tool_summary()` → **已移除**

**FC-only变更记录（v2.1新增）**:
- `TOOL_CALL_RULES` 合并 `AVOID_REPEAT_RULES`，移除FC冗余规则#1/#3/#4（2026-06-12）
- `build_full_system_prompt()` 从8段精简为4段（2026-06-12）
- `get_rollback_instructions()` 方法删除（2026-06-12）
- `candidates_hint`/`cross_tool_hint` / `executed_tool_summary` **全部移除**（2026-06-12 北京老陈）

### 3.3 各分类 get_core_system_prompt() + get_tool_details() 内容概况

**FC-only重构（2026-06-11）**:
- `get_system_prompt()` 拆分为 `get_core_system_prompt()`（角色+业务规则）+ `get_tool_details()`（工具描述+示例）
- 系统信息 `_get_system_info()` 提到基类公共层，子类不再自行注入
- 所有子类的 `get_core_system_prompt()` 只包含**角色定义 + 业务规则**，不包含系统信息

| 分类 | `get_core_system_prompt()` 内容 | `get_tool_details()` 方式 | Examples | 额外规则 |
|------|-------------------------------|--------------------------|----------|---------|
| **file** | 互斥参数规则 + write_text_file规则 | 动态 `build_tool_descriptions()` | 3个决策示例 | 工具描述+示例都在get_tool_details |
| **system** | 角色定义 + 操作规则分类 | 动态 `build_tool_descriptions()` + `_build_examples(6)` | 6个 | FUND_RUNTIME分类 |
| **network** | 角色定义 | 动态 `build_tool_descriptions()` | 3个决策示例 | 工具描述+示例都在get_tool_details |
| **desktop** | 角色定义 | 动态 `build_tool_descriptions()` | 3个决策示例 | 工具描述+示例都在get_tool_details |
| **document** | 角色定义 | 动态 `build_tool_descriptions()` | 3个决策示例 | 工具描述+示例都在get_tool_details |
| **time** | 完整工具描述+示例（旧版） | 旧版无get_tool_details（未完全重构） | 4个 | get_core_system_prompt未实现，仍使用旧版结构 |

**注**: `time_prompts.py` 尚未完全重构到新的 `get_core_system_prompt()` + `get_tool_details()` 分裂结构，仍使用旧版整体式写法。

### 3.4 System Prompt 最终内容示例（file分类，FC-only）

```
【环境信息】
- 工作目录: C:\Users\xxx\project
- Git仓库: 是
- 当前日期: 2026-06-12

【当前系统】
Windows

【路径格式】
- 当前系统: C:\Users\xxx\file.txt 或 C:/Users/xxx/file.txt

【路径规则】
- 必须使用绝对路径...

【项目上下文】:
[README.md 内容]

【互斥参数规则 - 同一工具内禁止同时使用】:
- read_file: file_paths 单路径=单文件,多路径=批量
- edit_file: old_string 与 edits 互斥
...

【write_text_file content规则】:
- content 参数必须传实际文件内容...

【回答要求】:
- reasoning简短(1-2句),不要长篇分析
- 始终用中文回复

【停止条件】:
- 用户请求已完成,直接回答用户问题
- 遇到无法解决的错误,向用户报告原因和建议

【执行效率】:
- 同一工具成功后不要重复执行
- 已获取的信息直接使用,严禁二次获取
- 失败后换其他工具或参数,不要重试同一操作
- 连续3次不同方法都失败→停止尝试,向用户报告
```

**整个 System Prompt 的段数（v2.1精简化）**: 基类 4 段。

| 段号 | 段名 | 说明 |
|------|------|------|
| ① | `_get_system_info()` | 环境信息+OS+路径规则（基类公共） |
| ② | `_get_project_context()` | 项目上下文，有则追加（基类公共） |
| ③ | `get_core_system_prompt()` | 业务规则（分类特有） |
| ④ | `TOOL_CALL_RULES`(safety合并) | 回答要求+停止条件+执行效率+安全提醒 |

**v2.1移除**: 无 `get_tool_details()` 段、无 `get_rollback_instructions()` 段、无 `AVOID_REPEAT_RULES` 段；`candidates_hint`/`cross_tool_hint` 移至 `_call_llm` 每轮注入后亦已移除。

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
1. 确定操作类型(读取/写入/搜索/编辑/删除)
2. 检查路径是否存在,选择合适的文件工具
3. 执行操作并用中文总结结果
```

### 4.3 各分类 domain 值

| 分类 | _get_domain_name | _get_domain_steps |
|------|-----------------|-------------------|
| file | 文件管理 | 3步（确定操作类型/选择工具/执行总结） |
| system | 系统 | 3步（判断需求/按规则操作/总结） |
| network | 网络 | 3步（判断操作/选择工具/报告结果） |
| desktop | 桌面操作 | 3步（识别窗口/选择工具/确认结果） |
| document | 文檔处理 | 3步（分析需求/选择工具/总结） |
| time | 时间日期 | 3步（分析需求/选择工具/提供信息） |
| 基类默认 | 通用 | 3步（分析/使用工具/总结） |

---

## 五、Conversation History 管理

### 5.1 数据结构

**文件**: `message_builder.py:40-43`

```python
self.conversation_history: List[Dict[str, Any]] = []  # 正式历史
self.temp_history: List[Dict[str, Any]] = []           # 临时缓存(chunk累积用)
self.MAX_CONTEXT_CHARS = max_context_chars             # 上下文容量上限
```

### 5.2 消息类型（FC-only）

| role | 来源 | content值 | 说明 |
|------|------|-----------|------|
| `system` | init_history() 第1条 | 完整System Prompt | 始终在第1位 |
| `user` | init_history() 第2条 | Task Prompt | 始终在第2位 |
| `assistant` + `tool_calls` | _append_observation() FC协议 | content=None | FC协议工具调用（内含tool_call_id+function） |
| `tool` | _append_observation() FC协议 | observation文本 | FC协议工具结果（tool_call_id配对） |

**FC-only 变更**:
- 删除: `add_assistant()`（不再需要，FC协议由_append_observation统一处理）
- 删除: `TOOL_REMINDER` 标志位注入
- 删除: Text模式下 `user + [Tool Result]` 形式
- 新增: `fc_message_types.py` 定义类型化的 `FcMessage`（SystemMessage/UserMessage/AssistantMessage/ToolResultMessage）
- Observation前缀: `[Observation]`（非 `[Tool Result]`）

### 5.3 初始化

**文件**: `core_agent/initialize_run_state.py:15-32`

```python
self.message_builder.init_history(sys_prompt, task_prompt)
# → conversation_history = [
#     message_to_dict(SystemMessage(content=sys_prompt)),
#     message_to_dict(UserMessage(content=task_prompt))
#   ]
```

### 5.4 每轮变化（FC-only）

```
第0轮: [system, user]
第1轮: [system, user, assistant(tool_calls=...), tool(content="[Observation] ...")]
第2轮: [system, user,
         assistant(tool_calls=...1), tool(content=...1),
         assistant(tool_calls=...2), tool(content=...2)]
...
```

**注**: 每轮严格保证 `assistant(tool_calls)` → `tool` 配对，由 `_trim_fc_pairs()` 维护完整性。

### 5.5 prepare_messages_for_llm()

**文件**: `message_builder.py:117-130`

```python
def prepare_messages_for_llm(self) -> List[Dict[str, Any]]:
    self._cap_temp_history()  # temp_history 字符限制 <=50000
    messages = list(self.conversation_history)
    if self.temp_history:
        messages = messages + list(self.temp_history)
    return messages
```

### 5.6 _call_llm() — 纯FC精简调用

**文件**: `universal_agent.py:127-152`

```python
async def _call_llm(self):
    """调用LLM — 纯FC模式 — FC-only重构 2026-06-11 小沈"""
    self.llm_call_count += 1
    self.message_builder.trim_history()
    messages = self.message_builder.prepare_messages_for_llm()
    openai_tools = self._get_openai_tools()
    if not openai_tools:
        logger.error(f"[call_llm] 无可用工具, category={self.tool_category}")
    async for item in self._call_llm_fc_stream(messages, openai_tools):
        yield item
```

**FC-only变更**:
- 删除 TOOL_REMINDER 惰性注入（2026-06-11）
- 删除 Text模式降级分支
- 删除 _build_executed_tool_summary / _build_candidates_hint / _build_cross_tool_hint（2026-06-12 北京老陈）
- _call_llm() 只做 prepare + get_tools + stream，职责单一

### 5.7 历史裁剪 trim_history()（FC-only）

**文件**: `message_builder.py:141-215`

**条件**: 总字符 > MAX_CONTEXT_CHARS * 0.8（默认 > 120000字符，需保证 > 2 条非system消息）

**裁剪策略（FC-only精简版）**:

1. **消息分组**: 分为 `system_msgs` / `obs_list`(role=tool) / `assistant_msgs` 三组
2. **预算计算**: `available_budget = max(10000, MAX_CONTEXT_CHARS * 0.7 - system_chars)`
3. **从后往前扫描**: 从最新消息往最旧遍历
   - 遇到 `role: tool` 且有配对 `assistant(tool_calls)` → 成对保留
   - 遇到独立消息 → 直接保留
   - 超过budget时停止
4. **FC配对修剪**: `_trim_fc_pairs()` 确保 `assistant.tool_calls` ↔ `tool` 严格配对，移除孤儿消息
5. **兜底**: 若重组后 < 2 条，保留首2条 + 末8条

**FC-only 变更（2026-06-11）**:
- 删除: observation去重逻辑（FC模式下不再需要）
- 删除: text_msgs/tool_call_msgs分离（FC-only无text模式observation）
- 简化: 统一按原始顺序扫描，无复杂分类优先级

---

## 六、LLM 调用链路（FC-only）

### 6.1 调用栈

```
universal_agent._call_llm()   ← 纯FC模式
  └─ _call_llm_fc_stream()    ← FC-only: 无降级路径
      ├─ LLMClient.request_stream(messages, tools=tools, tool_choice="auto")
      │   └─ POST /chat/completions {model, messages, tools, tool_choice}
      │       
      ├→ 异常: yield ("response", {"type": "answer", "content": f"LLM调用异常: {e}"})
      ├→ stream_error: yield ("response", {"type": "answer", "content": f"LLM流式错误: ..."})
      └→ 正常: chunk.tool_calls 原生 → action/answer 分派
```

**关键变更（FC-only重构 2026-06-11）**:
- 删除: `_call_llm_text_stream()` （不再存在）
- 删除: `_convert_fc_messages_to_text()` （不再存在）
- 删除: `parse_llm_response.py` （不再存在，`chunk.tool_calls` 原生消费）
- 删除: `mode` 参数 （`request_stream` 不再有 mode 参数）

### 6.2 请求体构建

**文件**: `llm/client_sdk.py:25-49` `_build_request_body()`

```python
def _build_request_body(
    messages, model,
    max_tokens=None, temperature=None, seed=None,
    tools=None, tool_choice=None, stream=False,
) -> Dict:
    """统一构建 LLM 请求体 — FC-only: 无mode参数 — 小沈 2026-06-11"""
    body = {"model": model, "messages": messages}
    if max_tokens is not None: body["max_tokens"] = max_tokens
    if temperature is not None: body["temperature"] = temperature
    if seed is not None: body["seed"] = seed
    if stream: body["stream"] = True
    if tools:
        body["tools"] = tools
        if tool_choice: body["tool_choice"] = tool_choice
    return body
```

**FC-only变更**: 无 `mode` 参数，`tools` 不为 None 时始终注入 `tools`。

### 6.3 FC模式（唯一模式）

| 维度 | FC模式（唯一路径） |
|------|-------------------|
| **请求体** | `{messages, tools, tool_choice:"auto"}` |
| **LLM响应** | delta.tool_calls + delta.content 混合流 |
| **解析** | SSE流聚合 → `is_reasoning` 分流 → `chunk.tool_calls` 原生消费 |
| **异常** | yield answer + error message，不降级 |
| **stream_error** | yield answer + error message，不降级 |
| **无降级** | FC-only: 没有Text模式兜底，异常时直接返回错误信息 |

**注**: 自2026-06-11起,`_call_llm`为纯FC模式。`_call_llm_text_stream`/`_convert_fc_messages_to_text()` 已全部删除。`BaseAIService`中间层也已移除，LLM调用直接走`LLMClient`。

---



## 九、数据流最终形态（发给 LLM 的完整消息 — FC-only）

### 第0轮 messages 结构（FC-only）

```json
[
  {
    "role": "system",
    "content": "【环境信息】\n- 工作目录: C:\\Users\\xxx\\project\n- Git仓库: 是\n- 当前日期: 2026-06-12\n\n【当前系统】\nWindows\n\n【路径格式】\n- 当前系统: C:\\Users\\xxx\\file.txt\n\n【路径规则】\n- 必须使用绝对路径...\n\n【项目上下文】:\n[README.md内容]\n\n【互斥参数规则】:\n...\n\n# File Operation Tools\n\n  1. read_file - 读取文件内容\n  ...\n\n【工具调用规则】:\n...\n\n【停止条件】:\n...\n\n【操作失败时的处理步骤】:\n...\n\n【避免重复规则】\n..."
  },
  {
    "role": "user",
    "content": "Task: 读取桌面上的config.json文件\n\nCurrent time: 2026-06-10 15:00:00\n\n请完成此文件管理任务,按以下步骤:\n1. 确定操作类型(读取/写入/搜索/编辑/删除)\n2. 检查路径是否存在,选择合适的文件工具\n3. 执行操作并用中文总结结果\n"
  }
]
```

**注**: FC-only模式下，System Prompt**不包含** `OUTPUT_FORMAT` 段（格式由API的 `tool_calls` Schema约束）。Tool description可由 `exclude_tool_details_from_prompt` 配置跳过（由FC Schema承载）。

### 第1轮 messages 结构（第1次工具调用后，FC-only）

```json
[
  {"role": "system", "content": "...（完整System Prompt）..."},
  {"role": "user", "content": "Task: 读取桌面上的config.json文件..."},
  {"role": "assistant", "tool_calls": [
    {"id": "call_xxx", "type": "function",
     "function": {"name": "read_file", "arguments": "{\"file_paths\": [\"C:/Users/xxx/Desktop/config.json\"]}"}}
  ]},
  {"role": "tool", "content": "[Observation] success - 文件读取成功\n数据: {\"content\": \"...\"}", "tool_call_id": "call_xxx"}
]
```

**FC-only 关键特征**:
- `assistant` 消息使用 `tool_calls` 字段（非 `content`）
- `observation` 使用 `role: tool`（非 `user`），带 `tool_call_id` 配对
- 无 `TOOL_REMINDER` 动态注入
- 无 `[Tool Result]` 前缀，使用 `[Observation]` 前缀

### 第N轮 messages 结构（FC-only）

```json
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "Task: ..."},
  {"role": "assistant", "tool_calls": [{...}]},
  {"role": "tool", "content": "[Observation] ...", "tool_call_id": "..."},
  {"role": "assistant", "tool_calls": [{...}]},              // 后续轮次
  {"role": "tool", "content": "[Observation] ...", "tool_call_id": "..."},
]
```

**FC-only 特征总结**:
- 所有 observation 使用 `role: tool` + `tool_call_id`
- 所有 assistant 工具调用使用 `tool_calls` 协议
- 无 `user + [Tool Result]` 形式
- 无 `【已执行工具摘要】` system消息
- `_trim_fc_pairs()` 保证配对完整性

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
| **第8遍** | **2026-06-12 代码复核** | **小欧** | **15+** | **全章节复核: 文件清单更新(1.3)/数据流重塑(2)/System Prompt 8段组装(3)/Task Prompt微调(4)/Conversation History FC-only(5)/LLM调用链路FC-only(6)/数据流FC-only(9)** |
| **第9遍** | **2026-06-12 12:22:05** | **小欧** | **5** | **FC-only精简化改造更新: 数据流图(2)/3.1_system_prompt简化/3.2组装4段/3.4示例与段表/5.6_call_llm注入hints** |

---

**文档完成时间**: 2026-06-10 15:21:00
**版本v1.2更新时间**: 2026-06-11 (代码同步校验)
**版本v1.2更新人**: 小欧
**更新内容**: 逐节核对代码，修复9处差异（_get_system_prompt guard+strategy, build_full_system_prompt strategy+AVOID_REPEAT_RULES, _call_llm FC-only+tool_reminder, trim_history FC配对保护, TOOL_CALL_RULES标题, 降级路径）

**版本v2.0更新时间**: 2026-06-12 (代码复核)
**版本v2.0更新人**: 小欧
**更新内容**: 逐章复核本地代码，更新全部章节以匹配FC-only架构 — 共计15+处差异修复（文件清单、数据流图、System Prompt 8段组装、Task Prompt示例修正、Conversation History FC-only、LLM调用链路FC-only、数据流最终形态FC-only）

**版本v2.1更新时间**: 2026-06-12 12:22:05
**版本v2.1更新人**: 小欧
**更新内容**: FC-only精简化改造: TOOL_CALL_RULES合并AVOID_REPEAT_RULES; build_full_system_prompt从8段→4段(移除rollback/AVOID_REPEAT/get_tool_details可选段, safety合并入规则段); candidates_hint+cross_tool_hint移至_call_llm每轮注入

**编写人**: 小沈
