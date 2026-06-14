# Agent-工具-意图系统流程分析

**创建时间**: 2026-06-11  
**版本**: v1.0  
**编写人**: 小沈  
**复查**: 代码级逐行验证

---

## 一、完整流程链路

```
用户请求 "读取E:\test.txt"
    ↓
chat_router.py:24 → POST /chat
    ↓
chat_stream_v2.py:48 → detect_intent()
    ↓
CRSS评分 → ToolCategory.FILE → intent_type="file"
    ↓
AgentFactory.create("file") → resolve_agent_config("file")
    ↓
AGENT_REGISTRY["file"] → AgentConfig(category=FILE, prompt_class=FileOperationPrompts)
    ↓
UniversalAgent.__init__()
    ├─ super().__init__() → BaseAgent.__init__()
    │   ├─ AgentInitializer._init_llm()
    │   ├─ AgentInitializer._init_state()
    │   ├─ AgentInitializer._init_messages()
    │   ├─ ToolManager(self).init_tools()  ← 此时 self.config 尚未设置!
    │   └─ ToolRetryEngine(self._tools_dict)
    ├─ self.config = config    ← 设置在 super().__init__() 之后
    └─ self.prompts = config.prompt_class()
    ↓
run_react_cycle(agent, task, ...)
    ↓
_initialize_run_state()
    ├─ _get_system_prompt() → build_full_system_prompt()
    ├─ _get_task_prompt(task)
    └─ message_builder.init_history(sys_prompt, task_prompt)
    ↓
循环开始
    ↓
_call_llm()
    ├─ message_builder.trim_history()
    ├─ messages = prepare_messages_for_llm()
    ├─ executed_summary = _build_executed_tool_summary()
    ├─ openai_tools = _get_openai_tools()
    └─ _call_llm_fc_stream(messages, openai_tools)
    ↓
_call_llm_fc_stream()
    ├─ llm_client.request_stream(messages, tools=openai_tools)
    ├─ 流式聚合 tool_calls
    ├─ 解析 full_content → parsed JSON
    └─ yield ("response", {"type": "action", "tool_name": "read_file", ...})
    ↓
_process_single_step()
    ├─ 收集 response dict
    ├─ parsed_type = "action"
    └─ handle_action(agent, parsed, ...)
    ↓
handle_action()
    ├─ check_safety_and_confirm() → safety_checker.check_before_execute()
    ├─ execute_tools() → agent._execute_tool("read_file", params)
    ├─ build_observation() → 构建 observation
    └─ _update_message_builder() → add_observation(obs_text, fc_context)
    ↓
add_observation()
    ├─ _prepare_observation_text() → 截断 + 归一化
    ├─ _append_observation() → assistant(tool_calls) + role:tool
    └─ trim_history()
    ↓
循环继续 → _call_llm() → LLM 看到 observation → 返回 answer → FinalStep → COMPLETED
```

---

## 二、逐环节验证结果

### 2.1 用户请求 → 意图识别

**代码路径**: `chat_stream_v2.py:48` → `detect_intent_v2()` → `CRSS评分` → `ToolCategory` → `intent_type`

| 检查项 | 结果 | 说明 |
|--------|------|------|
| CRSS评分能否识别中文意图 | ✅ | 关键词+中文关键词双通道 |
| ToolCategory → intent_type 映射 | ✅ | `_TOOLCATEGORY_TO_INTENT` 覆盖5个分类 |
| candidates 返回值类型 | ⚠️ | 返回 `ToolCategory.value` 字符串（如"net_process"），非 intent_type |

### 2.2 意图 → Agent创建

**代码路径**: `AgentFactory.create()` → `resolve_agent_config()` → `AGENT_REGISTRY`

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 5个intent_type都有配置 | ✅ | file/system/network/document/desktop |
| config.category 与 ToolCategory 对应 | ✅ | FILE/FUND_RUNTIME/NET_PROCESS/DOC_CONTENT/SCREEN |
| extra_categories 配置 | ⚠️ | system配置了`extra_categories=[FILE]`，但初始化顺序有问题 |

### 2.3 Agent初始化

**代码路径**: `UniversalAgent.__init__()` → `BaseAgent.__init__()` → `ToolManager.init_tools()`

| 检查项 | 结果 | 说明 |
|--------|------|------|
| self.config 设置时机 | 🔴 **P0** | `self.config = config` 在 line 59，在 `super().__init__()` line 48 之后 |
| extra_categories 加载 | 🔴 **P0** | `ToolManager.init_tools()` 在 super().__init__ 中执行，此时 self.config 为 None |
| meta工具加载 | ✅ | 从 META_TOOL_NAMES 加载到 _tools_dict |
| 分类工具加载 | ✅ | 从 tool_registry 加载 |
| extra_categories 加载 | 🔴 **P0** | 永远不会执行（config 为 None） |

### 2.4 工具加载 → LLM可见性

**代码路径**: `ToolManager.init_tools()` → `_tools_dict` → `_get_openai_tools()` → FC tools

| 检查项 | 结果 | 说明 |
|--------|------|------|
| _tools_dict 包含所有工具 | ✅ | meta + 分类 + extra（如果加载了） |
| _get_openai_tools 过滤逻辑 | 🔴 **P1** | `category=self.tool_category` 时排除 FUND_RUNTIME 的 meta 工具 |
| 单分类agent看不到meta工具 | 🔴 **P1** | FILE agent 看不到 get_time/tool_help 等 |

### 2.5 ReAct循环 → LLM调用

**代码路径**: `_call_llm()` → `_call_llm_fc_stream()` → `llm_client.request_stream()`

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 消息准备 | ✅ | conversation_history + temp_history + executed_summary |
| FC工具传递 | ✅ | openai_tools 传入 request_stream |
| 流式聚合 | ✅ | tool_call跨chunk聚合 |
| 响应解析 | ✅ | parse_json → action/answer 分支 |
| 原始日志记录 | ✅ | 完整记录LLM原始响应 |

### 2.6 Handler分派 → 工具执行

**代码路径**: `_process_single_step()` → `handle_action()` → `execute_tools()` → `build_observation()`

| 检查项 | 结果 | 说明 |
|--------|------|------|
| handler分派 | ✅ | _TYPE_HANDLERS dict: action→handle_action, answer→handle_answer |
| 安全检查 | ✅ | check_before_execute → blocked/requires_confirmation/allowed |
| 工具执行 | ✅ | 并行/串行，超时保护 |
| observation构建 | ✅ | 包含tool_name/tool_params/observation/status |
| fc_context传递 | ✅ | 从parsed dict提取，传给add_observation |

### 2.7 observation写入 → conversation_history

**代码路径**: `add_observation()` → `_append_observation()` → conversation_history

| 检查项 | 结果 | 说明 |
|--------|------|------|
| FC协议格式 | ✅ | assistant(tool_calls) + role:tool |
| tool_call_id | ⚠️ **P1** | 空tool_call_id可能产生（LLM未返回id时） |
| _trim_fc_pairs | ✅ | 确保配对完整性 |
| trim_history | ✅ | 按预算裁剪，保留配对 |

### 2.8 意图候选提示

**代码路径**: `_build_candidates_hint()` → `resolve_agent_config(c)`

| 检查项 | 结果 | 说明 |
|--------|------|------|
| candidates 来源 | ✅ | CRSS评分返回 |
| candidates 类型 | ⚠️ **P2** | ToolCategory.value（如"net_process"） |
| resolve_agent_config 处理 | ⚠️ **P2** | normalize_intent("net_process") → INTENT_MAPPING无此key → fallback "system" |
| 提示文本准确性 | ⚠️ **P2** | network/document/desktop候选都显示为"基础运行时(system)" |

---

## 三、问题汇总

| 编号 | 严重性 | 问题 | 文件:行 | 影响 |
|------|--------|------|---------|------|
| P0-1 | 🔴 | `self.config` 在 `super().__init__()` 之后设置，extra_categories 永远不加载 | universal_agent.py:48+59 | system agent 无法使用 FILE 工具 |
| P1-1 | 🟡 | meta工具(FUND_RUNTIME)对单分类agent不可见 | universal_agent.py:250 + tool_manager.py:29 | FILE/Desktop agent 看不到 get_time/tool_help |
| P1-2 | 🟡 | 空tool_call_id可能产生 | universal_agent.py:208 + message_builder.py:77 | FC协议违规，API 400错误 |
| P2-1 | 🔵 | candidates hint显示错误分类名 | universal_agent.py:86 + intent_mapper.py:28 | LLM收到误导性候选提示 |
| P2-2 | 🔵 | 并行工具调用产生过多assistant消息 | action_handler.py:131-138 | token浪费，轻微影响 |

---

## 四、非问题确认（已验证无误）

| 检查项 | 结果 |
|--------|------|
| AGENT_REGISTRY 覆盖所有5个ToolCategory | ✅ |
| intent_mapper INTENT_MAPPING 覆盖所有CRSS名 | ✅ |
| 无循环导入（agent↔tools/agent↔prompts） | ✅ |
| tool_retry_engine 无finish死代码 | ✅ |
| _trim_fc_pairs 正确保护配对完整性 | ✅ |
| _process_single_step max_steps保护 | ✅ |
| handle_answer 空内容→FAILED | ✅ |
| 三方数据一致性验证（SSE vs DB） | ✅ |

---

**分析完成时间**: 2026-06-11
