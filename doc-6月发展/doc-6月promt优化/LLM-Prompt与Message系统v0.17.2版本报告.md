# LLM Prompt 与 Message 全系统分析报告（基于当前代码）

**创建时间**: 2026-06-25 13:25:18
**更新时间**: 2026-06-25 15:30:00
**版本**: v1.1
**编写人**: 小欧
**审核人**: 小健
**分析范围**: 从用户输入到 LLM API 调用的完整 Prompt/Message 构建链路

---

## 版本历史

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-25 13:25:18 | 小欧 | 基于当前代码状态全新编写 |
| v1.1 | 2026-06-25 15:30:00 | 小健 | 修正错误描述，更新为与代码一致的状态 |

---

## 一、分析说明

### 1.1 分析目标

- 全面梳理当前代码从用户输入到 LLM 调用的 Prompt/Message 构建链路
- 记录每一步的状态，输出可执行改进建议

### 1.2 分析范围文件清单

| 模块 | 文件 |
|------|------|
| **SSE运行器** | `services/react_sse_wrapper/run_sse_stream.py` |
| **Agent核心** | `services/agent/universal_agent.py`, `services/agent/core_agent/base_agent.py` |
| **ReAct循环** | `services/agent/core_agent/react_cycle.py`, `services/agent/core_agent/initialize_run_state.py` |
| **LLM调用** | `services/agent/llm_caller.py` |
| **Message管理** | `services/agent/message_builder.py`, `services/agent/agent_utils/fc_message_types.py` |
| **Prompt构建** | `services/prompts/system_prompts.py`, `services/prompts/system_adapter.py`, `services/prompts/project_context.py` |
| **Prompt日志** | `utils/prompt_logger.py` |
| **Steps类型** | `services/agent/steps/action_step.py`, `chunk_step.py`, `thought_step.py`, `observation_step.py`, `final_step.py`, `error_step.py`, `meta_step.py`, `base.py` |
| **LLM SDK** | `services/llm/client_sdk.py` |
| **常量** | `constants.py` |

---

## 二、完整数据流

```
用户输入 → run_sse_stream.py
  │
  ├─ UniversalAgent(task_id)  ← 直接实例化，无AgentFactory
  │   └─ _INITIAL_CATEGORIES = {FUNDAMENTAL, SHELL, FILE}
  │      └─ 其余分类通过 tool_search 动态注入
  │
  ├─ agent.run_react_cycle(task, context, task_id)
  │   └─ react_cycle.py
  │       │
  │       ├─ initialize_run_state(agent, task, task_id, context)
  │       │   ├─ agent._get_system_prompt()
  │       │   │   └─ PromptBuilder.build_full_system_prompt()
  │       │   │       = 5段(见第三章)
  │       │   ├─ prompt_logger.log_system_prompt()
  │       │   ├─ prompt_logger.log_task_prompt()
  │       │   ├─ agent.message_builder.init_history(sys_prompt, task)
  │       │   │   = [SystemMessage, UserMessage]
  │       │   └─ _inject_conversation_history()  ← 多轮对话支持
  │       │
  │       └─ 每轮循环: _process_single_step()
  │           ├─ call_llm(agent)  ← llm_caller.py
  │           │   ├─ message_builder.trim_history()       ← 容量裁剪
  │           │   ├─ prepare_messages_for_llm()           ← 组装消息
  │           │   ├─ prompt_logger.log_llm_call()         ← 记录请求
  │           │   └─ call_llm_fc_stream(messages, tools)  ← 纯FC
  │           │       └─ LLMClient.request_stream()       ← POST /chat/completions
  │           │           └─ chunk.tool_calls原生消费     ← 无JSON roundtrip
  │           │
  │           ├─ action_handler(action)  ← tool_calls分派
  │           │   ├─ check_safety_and_confirm()
  │           │   ├─ execute_tools()
  │           │   └─ build_observation() → message_builder.add_observation()
  │           │
  │           └─ answer_handler(answer)  ← 文本回复分派
  │               └─ agent.status = COMPLETED
  │
  └─ 每步 → prompt_logger.log_step_yield()  ← 所有类型(含chunk)
     └─ format_agent_sse() → yield SSE字符串到前端
```

---

## 三、System Prompt 构建

### 3.1 构建入口

**文件**: `universal_agent.py:68-71`

```python
def _get_system_prompt(self) -> str:
    if not hasattr(self, 'prompts') or not self.prompts:
        return "System: 通用助手"
    return self.prompts.build_full_system_prompt()
```

### 3.2 单一 PromptBuilder 类

**文件**: `services/prompts/system_prompts.py` `PromptBuilder`

当前架构**没有分类子类**（如SystemPrompts/NetworkPrompts等）。所有Agent共用同一个`PromptBuilder`实例。

`build_full_system_prompt()` 组装顺序：

| 顺序 | 段名 | 来源 | 说明 |
|------|------|------|------|
| ① | `get_core_system_prompt()` | `PromptBuilder.get_core_system_prompt()` | 角色定义+业务规则（硬编码长字符串） |
| ② | `_get_project_context()` | `project_context.load_project_context()` | 读取OmniAgent.md（如有） |
| ③ | `_get_system_info()` | `system_adapter.get_system_prompt()` | 系统信息（OS/路径规则） |
| ④ | `_get_project_root_info()` | `config.get_project_root()` | 项目根目录路径 |
| ⑤ | `TOOL_CALL_RULES` | 类变量 | 文件类型→工具映射规则 |

### 3.3 各段内容详解

**① get_core_system_prompt()** — 一个包含8个子段的长字符串：

| 子段 | 功能 |
|------|------|
| `<角色>` | OmniAgent全能助手定义 |
| `<任务分析与处理规则>` | 任务分解→计划→工具选择→执行 |
| `<回答要求>` | reasoning简短+中文回复 |
| `<执行纪律>` | 4条铁律（不重复、优先专业工具、搜tool_search、不伪造） |
| `<工具参数复核>` | 调用前核查3遍参数 |
| `<tool_search 使用说明>` | 11种搜索场景的关键词模板 |
| `<安全规则>` | 危险操作先确认 |
| `<任务检查（铁律）>` | 复盘任务+逐条检查子任务 |

**② _get_project_context()**: 读取项目根目录下`OmniAgent.md`文件，最多8000字符。

**③ _get_system_info()**: 调用`system_adapter.get_system_prompt()`，组装3段：

```
【环境信息】
- 项目根目录: {root}
- Git仓库: {yes/no}
- 当前时间: {now}

【当前系统】{Windows/Linux}

【路径格式】{Windows格式/Linux格式}

【路径规则】
- 禁止用 ~ 表示家目录
- ❌ 中文路径禁止翻译或转换!
```

**④ _get_project_root_info()**: 从config读取项目根目录路径。

**⑤ TOOL_CALL_RULES**: 类变量，包含文本文件/Office文档/媒体文件的读写工具映射规则。

### 3.4 代码状态说明

`build_full_system_prompt()` 方法（第119-148行）代码完整，功能正常：

- ✅ **TOOL_CALL_RULES已被正确追加** — 代码有5个`parts.append()`调用（包含TOOL_CALL_RULES）
- ✅ **无孤立字符串** — 代码干净，无多余字符串
- ⚠️ **docstring顺序不一致** — 文件头部docstring与实际代码顺序不一致，需要更新文档但功能正常
- ✅ **完整System Prompt包含5部分**，顺序为：
  1. `get_core_system_prompt()` — 角色+业务规则
  2. `_get_project_context()` — 项目上下文(OmniAgent.md)
  3. `_get_system_info()` — 系统信息(OS/路径规则)
  4. `_get_project_root_info()` — 项目根目录
  5. `TOOL_CALL_RULES` — 文件类型→工具映射规则

---

## 四、Task Prompt 构建

### 4.1 当前状态：Task Prompt已被删除（设计决策）

与v2.2旧版报告不同，**当前代码不包含 `get_task_prompt()` 方法**，这是FC-only架构的设计决策。

Task Prompt直接在 `initialize_run_state.py:58` 构建：

```python
agent.message_builder.init_history(sys_prompt, task)
```

其中 `task` 即用户原始输入消息。也就是说 **Task Prompt = 用户原始消息原文**，没有额外的步骤说明、domain信息。

### 4.2 影响

LLM收到的是原始用户输入，没有任何任务分解指导。任务分解完全依赖System Prompt中的`<任务分析与处理规则>`和`<执行纪律>`的文字说明。

---

## 五、Conversation History 管理

### 5.1 数据结构

**文件**: `message_builder.py:38-41`

```python
self.conversation_history: List[Dict[str, Any]] = []
self.temp_history: List[Dict[str, Any]] = []
self.MAX_CONTEXT_CHARS = max_context_chars  # 默认150000
```

### 5.2 消息类型（FC-only）

| role | 来源 | content值 | 说明 |
|------|------|-----------|------|
| `system` | `init_history()` 第1条 | 完整System Prompt | 始终在第1位 |
| `user` | `init_history()` 第2条 | 用户原始消息 | 始终在第2位 |
| `assistant` + `tool_calls` | `_append_observation()` | content=None | FC协议工具调用 |
| `tool` | `_append_observation()` | observation文本 | FC协议工具结果 |

类型定义在 `fc_message_types.py`（5种Pydantic模型）：
- `SystemMessage` — `role: "system"`, `content: str`
- `UserMessage` — `role: "user"`, `content: str`
- `AssistantMessage` — `role: "assistant"`, content+tool_calls可选
- `ToolResultMessage` — `role: "tool"`, content+tool_call_id
- `ToolCall` / `ToolFunction` — tool_calls的子结构

### 5.3 初始化（第0轮）

```
[system, user]
```

### 5.4 每轮变化（FC-only）

```
第0轮: [system, user]
第1轮: [system, user, assistant(tool_calls=...), tool(content=...)]
第N轮: [system, user, assistant(tool_calls=...1), tool(content=...1), assistant(tool_calls=...N), tool(content=...N)]
```

每轮严格保证 `assistant(tool_calls)` → `tool` 配对，由 `_trim_fc_pairs()` 维护完整性。

### 5.5 历史裁剪 `trim_history()`

**文件**: `message_builder.py:144-158`

触发条件：总字符 > `MAX_CONTEXT_CHARS * 0.8`（默认>120000字符）

裁剪策略：
1. **消息分组** → system/observation(tool)/assistant 三组
2. **预算计算** → `available_budget = max(10000, MAX_CONTEXT_CHARS * 0.7 - system_chars)`
3. **从后往前扫描** → 保留`tool+assistant`配对，强制保留每种工具的首次observation
4. **FC配对修剪** → `_trim_fc_pairs()`确保配对完整性
5. **兜底** → 重组后<2条时保留首2条+末8条

---

## 六、LLM 调用链路（FC-only）

### 6.1 调用栈

```
call_llm(agent)  ← llm_caller.py:17
  ├─ trim_history()
  ├─ prepare_messages_for_llm()
  ├─ get_openai_tools()
  ├─ prompt_logger.log_llm_call()  ← 记录请求消息+工具定义
  └─ call_llm_fc_stream(messages, tools)
      └─ LLMClient.request_stream(messages, tools, tool_choice="auto")
          └─ POST /chat/completions {messages, tools, tool_choice:"auto"}
          
      ├─ 异常 → yield ("response", {"type": "answer", "content": "LLM调用异常: ..."})
      ├─ stream_error → yield ("response", {"type": "answer", "content": "LLM流式错误: ..."})
      └─ 正常 → chunk.tool_calls原生消费
          ├─ 有tool_calls → _build_tool_calls_response() → yield action
          └─ 无tool_calls → _build_answer_response() → yield answer
```

### 6.2 请求体构建

**文件**: `client_sdk.py:26-61`

```python
def _build_request_body(
    messages, model,
    max_tokens=None, temperature=None, seed=None,
    tools=None, tool_choice=None, stream=False,
    parallel_tool_calls=None, stream_options=None,
) -> Dict:
```

- **无`mode`参数** — FC-only
- `parallel_tool_calls`: 如果工具包含 FILE_OPERATION_TOOL 则自动禁用
- 工具注入规则：`tools != None` 时始终注入

### 6.3 FC模式（唯一模式）

| 维度 | FC模式 |
|------|--------|
| **请求体** | `{messages, tools, tool_choice:"auto"}` |
| **LLM响应** | `delta.tool_calls` + `delta.content` 混合流 |
| **解析** | SSE流聚合 → `chunk.tool_calls` 原生消费（无JSON roundtrip） |
| **并行工具** | 依赖模型能力，部分工具禁用并行 |
| **异常** | yield answer + error message，不降级 |
| **无降级** | 纯FC-only，没有Text模式兜底 |

---

## 七、Prompt 日志系统

### 7.1 日志文件结构

**文件**: `prompt_logger.py`

每次请求生成一个JSON文件，存放在 `backend/logs/prompt-logs/` 目录。

文件名格式：`prompt_{ai_id_short}+{timestamp}.json`

### 7.2 JSON 文件结构

```json
{
  "基本信息": {
    "时间戳": "...",
    "会话ID": "...",
    "用户消息ID": ...,
    "AI消息ID": ...,
    "用户消息": "..."
  },
  "Prompt组装过程": [
    {"步骤": "运行时系统Prompt注入", "类型": "系统Prompt", "内容": "...", "内容长度": ...},
    {"步骤": "任务Prompt生成", "类型": "任务Prompt", "内容": "...", "内容长度": ...}
  ],
  "LLM调用记录": [
    { "轮次": 1, "调用类型": "tools", "模型": "...", "提供商": "...",
      "消息统计": {...}, "消息摘要": [...], "工具定义": [...], "工具数量": ...},
    { "轮次": 1, "返回类型": "action/answer", "解析结果": "...", "原始响应": "...", ...}
  ],
  "步骤产出": [
    { "轮次": 1, "步骤": 1, "步骤类型": "start", "数据": {...} },
    { "轮次": 2, "步骤": 2, "步骤类型": "action_tool", "数据": {...} },
    { "轮次": 2, "步骤": 2, "步骤类型": "chunk", "数据": {...} },
    ...
  ]
}
```

### 7.3 记录的Step类型

当前（2026-06-24修复后）所有step类型都记录到步骤产出节：
- `start`, `chunk`, `thought`, `action_tool`, `observation`, `final`, `error`, `interrupted`等

### 7.4 LLM调用记录vs步骤产出的关系

| 对比维度 | LLM调用记录 | 步骤产出 |
|---------|------------|---------|
| **粒度** | 每次LLM请求1条记录+1条响应 | 每步yield 1条 |
| **内容** | 完整的消息摘要+工具定义 | step dict |
| **用途** | 调试LLM输入/输出 | 验证SSE-DB一致性 |

---

## 八、Agent 类体系

### 8.1 类结构（扁平化）

```
BaseAgent(ABC)  ← core_agent/base_agent.py (78行)
  └─ UniversalAgent  ← universal_agent.py (75行)
```

**无** AgentFactory、**无** CRSS intent scoring、**无** 分类子类。

### 8.2 UniversalAgent 初始化

```python
_INITIAL_CATEGORIES = {FUNDAMENTAL, SHELL, FILE}

class UniversalAgent(BaseAgent):
    def __init__(self, llm_client, task_id, ...):
        self._loaded_categories = set(initial_categories)
        self.prompts = PromptBuilder()
        self._tool_cache = TTLCache(300)
        self._patch_search_desc()
```

初始注入3个工具分类给LLM。其余分类（DESKTOP, NETWORK, DOCUMENT, WIN_REGISTRY等）通过 `tool_search` 工具动态注入。

### 8.3 Handler 分派

**文件**: `core_agent/handlers/`

| Handler | 文件 | 职责 |
|---------|------|------|
| `action_handler` | `action_handler.py:326` | 工具调用处理：安全检查→执行→构建observation |
| `answer_handler` | `answer_handler.py:15` | 文本回复处理：ThoughtStep→FinalStep+保存 |

---

## 九、当前代码状态与改进建议

### 9.1 `build_full_system_prompt()` 代码完整性问题（已修复）

**实际状态**: 代码完整，功能正常

`system_prompts.py:119-148`:
- ✅ **TOOL_CALL_RULES 已被正确追加** — 代码有5个`parts.append()`调用（包含TOOL_CALL_RULES）
- ✅ **无孤立字符串** — 代码干净，无多余字符串
- ⚠️ **docstring 顺序不一致** — 文件头部docstring与实际代码顺序不一致，但功能正常
- ✅ **完整System Prompt包含5部分**：
  1. `get_core_system_prompt()` — 角色+业务规则
  2. `_get_project_context()` — 项目上下文(OmniAgent.md)
  3. `_get_system_info()` — 系统信息(OS/路径规则)
  4. `_get_project_root_info()` — 项目根目录
  5. `TOOL_CALL_RULES` — 文件类型→工具映射规则

**影响评估**: System Prompt完整包含文件类型→工具映射规则，LLM能正确选择工具。

### 9.2 无 Task Prompt 指导（设计决策）

**实际状态**: 设计决策，非bug

- ✅ `get_task_prompt()` 确实已被删除 — 符合FC-only架构设计
- ✅ LLM直接接收用户原始消息 — 简化架构，依赖System Prompt中的规则
- ✅ 完全依赖System Prompt文字规则 — 符合KISS-DIRECT原则

**改进建议**: 如果需要任务分解指导，可考虑在System Prompt中增强相关规则。

### 9.3 所有Agent共用同一个 PromptBuilder（设计决策）

**实际状态**: 设计决策，非bug

- ✅ 当前只有1个UniversalAgent — 扁平化设计
- ✅ 所有任务使用同一个`get_core_system_prompt()` — 简化维护
- ⚠️ 未来扩展性 — 如需分类特定规则，可扩展设计

**改进建议**: 保持当前简洁设计，需要时再扩展。

---

## 十、与v2.2旧版报告的差异总结

| 对比项 | 旧版(v2.2, 2026-06-12) | 当前代码(2026-06-25) | 变化 |
|--------|----------------------|-------------------|------|
| 文件基础 | `base_prompt_template.py` | `services/prompts/system_prompts.py` | 路径+文件名改变 |
| 分类子类 | system/network/desktop/document/file/meta | **全部删除** | 扁平化为1个PromptBuilder |
| `get_task_prompt()` | 存在，组装3步指导 | **已删除** | LLM直接收原始消息 |
| AgentFactory+CRSS | 存在 | **已删除** | 直接实例化UniversalAgent |
| `_call_llm()`位置 | universal_agent.py方法 | `llm_caller.py`独立函数 | 拆出独立模块 |
| `chunk`记录 | 被跳过 | **全部记录** | 2026-06-24修复 |
| `build_full_system_prompt()`段数 | 4段 | **5段（完整）** | 新增_project_root_info + TOOL_CALL_RULES |
| LLM SDK `_build_request_body` | 无`mode`参数 | 增加parallel_tool_calls控制 | 功能增强 |
| **问题修复状态** | 存在多个问题 | **大部分已修复** | 代码质量提升 |

---

**文档更新时间**: 2026-06-25 15:30:00
**版本**: v1.1
**编写人**: 小欧
**审核人**: 小健
**审核说明**: 根据代码实际状态修正了错误描述，确认`build_full_system_prompt()`代码完整，TOOL_CALL_RULES正确追加，无孤立字符串。问题9.1实际不存在，9.2和9.3为设计决策。
