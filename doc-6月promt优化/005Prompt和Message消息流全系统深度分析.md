# 后端 Prompt 和 Message Conversation History 全系统深度分析

> 作者: Agnes-2.0-Flash (AI Agent)
> 复查次数: 5遍
> 分析日期: 2026-06-10
> 代码位置: /mnt/g/OmniAgentAs-desk/backend (304个Python文件)

---

## 目录

1. [系统概览与核心架构](#1-系统概览与核心架构)
2. [Prompt 模板系统](#2-prompt-模板系统)
3. [Message 构建与 conversation_history 管理](#3-message-构建与-conversationhistory-管理)
4. [Agent ReAct 循环与消息流](#4-agent-react-循环与消息流)
5. [LLM 客户端调用](#5-llm-客户端调用)
6. [工具结果到 Observation 的转换](#6-工具结果到-observation-的转换)
7. [DB 持久化: Execution Steps 存储](#7-db-持久化-execution-steps-存储)
8. [Prompt 日志系统](#8-prompt-日志系统)
9. [完整消息流图](#9-完整消息流图)
10. [不合理之处分析](#10-不合理之处分析)
11. [总结](#11-总结)

---

## 1. 系统概览与核心架构

### 1.1 消息流四层架构

```
API层 (FastAPI) ──→ Agent编排层 ──→ LLM调用层 ──→ 外部LLM API
     ↑                      ↑               ↑
     └──── DB持久化 ◄───────┘               └──→ SSE流式返回 ◄──┘
```

### 1.2 关键文件清单

**API入口:**
- `app/api/v1/chat/chat_router.py` — FastAPI 路由分发 (/chat/stream)
- `app/api/v1/chat/chat_stream_v2.py` — API层入口, 意图检测→任务注册→SSE流
- `app/api/v1/chat/models.py` — ChatMessage/ChatRequest Pydantic模型

**Agent核心:**
- `app/services/agent/core_agent/base_agent.py` — BaseAgent抽象基类(骨架)
- `app/services/agent/core_agent/react_cycle.py` — ReAct循环核心(薄调度)
- `app/services/agent/universal_agent.py` — 配置驱动通用Agent(含LLM调用)
- `app/services/agent/agent_factory.py` — 基于声明式配置创建Agent
- `app/services/agent/agent_config.py` — AgentConfig声明式注册表(5类意图)
- `app/services/agent/core_agent/agent_initializer.py` — Agent初始化逻辑
- `app/services/agent/core_agent/initialize_run_state.py` — 每次run状态初始化
- `app/services/agent/core_agent/handlers/` — 5个handler: action/answer/chunk/error/unknown
- `app/services/agent/tool_retry_engine.py` — 工具重试引擎

**消息构建:**
- `app/services/agent/message_builder.py` — conversation_history状态管理器
- `app/services/agent/agent_utils/message_utils.py` — 纯函数工具(消息构建/注入)
- `app/services/agent/llm_response_parser/` — LLM响应统一解析器

**Prompt模板:**
- `app/services/prompts/base_prompt_template.py` — BasePrompts抽象基类
- `app/services/prompts/file/file_prompts.py` — FileOperationPrompts
- `app/services/prompts/system/system_prompts.py` — SystemPrompts
- `app/services/prompts/network/network_prompts.py` — NetworkPrompts
- `app/services/prompts/document/document_prompts.py` — DocumentPrompts
- `app/services/prompts/desktop/desktop_prompts.py` — DesktopPrompts
- `app/services/prompts/middle/system_adapter.py` — 系统信息中间层(OS自适应)

**LLM调用:**
- `app/services/llm_core/llm_core.py` — BaseAIService (request/request_stream/chat)
- `app/services/llm/client_sdk.py` — SDK客户端创建

**工具系统:**
- `app/services/tools/registry.py` — 工具注册中心
- `app/services/tools/_response.py` — 工具返回结构(build_success/error/warning)
- `app/services/tools/tool_description.py` — 工具描述→OpenAI format

**Agent层工具结果:**
- `app/services/agent/agent_utils/tool_result_factory.py` — Agent层结果工厂
- `app/services/agent/observation_formatter.py` — 工具结果→LLM observation文本

**SSE流式输出:**
- `app/services/react_sse_wrapper/run_sse_stream.py` — 纯SSE流运行器
- `app/chat_stream.py` — SSE事件流处理统一模块(格式/保存/错误/辅助)

**步骤模型:**
- `app/services/agent/steps/` — 10个Step类型(ReasoningStep基类+9个子类)

**DB持久化:**
- `app/api/v1/conversation/save_execution_steps.py` — 保存执行步骤到DB
- `app/api/v1/conversation/insert_assistant_message.py` — 插入assistant消息
- `app/db/models/chat_models.py` — Session/Message Pydantic模型

**Prompt日志:**
- `app/utils/prompt_logger.py` — 每次请求的Prompt组装过程记录(JSON文件)

---

## 2. Prompt 模板系统

### 2.1 设计模式: 类继承 + 动态模块加载

系统采用声明式配置驱动,每种意图类型(File/System/Network/Document/Desktop)对应一个独立的Prompt模板类,继承自 `BasePrompts`。

**配置注册表 (`agent_config.py`):**

```
AGENT_REGISTRY (Dict[str, AgentConfig]):
  "file"    → FileOperationPrompts    (ToolCategory.FILE)
  "system"  → SystemPrompts           (ToolCategory.FUND_RUNTIME)
  "network" → NetworkPrompts          (ToolCategory.NET_PROCESS)
  "document"→ DocumentPrompts         (ToolCategory.DOC_CONTENT)
  "desktop" → DesktopPrompts          (ToolCategory.SCREEN)
```

每个 AgentConfig 包含:
- `intent_type`: 意图类型字符串
- `category`: ToolCategory枚举
- `prompt_module`: 模块路径 (如 "app.services.prompts.file.file_prompts")
- `prompt_class_name`: 类名 (如 "FileOperationPrompts")
- `agent_module/class_name`: Agent类 (默认 UniversalAgent)
- `rollback_enabled`: 是否启用回滚
- `max_steps`: 最大步数
- `extra_categories`: 额外工具分类

**运行时动态加载:** `AgentConfig.prompt_class` 属性通过 `importlib.import_module` 延迟加载Prompt类,并使用 `_prompt_class` 缓存。

### 2.2 BasePrompts 基类 — Prompt组装架构

**`build_full_system_prompt()` 组装顺序 (唯一入口):**

```
① get_system_prompt()       — 分类特有: 角色定义 + 工具详情 + 示例
② OUTPUT_FORMAT             — 公共: JSON输出格式(含退出规则)
③ TOOL_CALL_RULES           — 公共: 工具调用规则
④ get_safety_reminder()     — 分类特有: 安全提醒(子类覆盖,默认空)
⑤ get_rollback_instructions() — 公共: 回滚说明
⑥ 【避免重复规则】          — 硬编码在基类中
```

**运行时追加 (@UniversalAgent._get_system_prompt):**

```
⑦ _build_candidates_hint()  — 动态: 候选意图提示 (意图检测不确定时注入)
⑧ _build_cross_tool_hint()  — 动态: 跨分类工具提示 (多分类工具加载时注入)
```

### 2.3 OUTPUT_FORMAT 字段规范

JSON输出,只能返回两种情况:
- **情况1 (调用工具)**: `{"thought": "...", "reasoning": "...", "tool_name": "...", "tool_params": {...}}`
- **情况2 (任务完成)**: `{"thought": "...", "reasoning": "...", "tool_name": "finish", "tool_params": {"result": "..."}}`

强制要求: thought, reasoning, tool_name, tool_params 四个字段均为必需。禁止同时返回多个tool_name,禁止纯文本回复代替工具调用。

### 2.4 中间层系统适配器 (SystemAdapter)

`prompts/middle/system_adapter.py` 根据服务器操作系统动态生成系统信息Prompt:
- 路径格式示例 (Windows/Linux/macOS)
- 路径规则 (必须绝对路径,禁止相对路径,禁止~)
- 命令格式 (可选注入,仅ShellAgent时开启)
- 含 `@functools.lru_cache(maxsize=1)` 单例缓存

### 2.5 工具描述动态生成

`BasePrompts.build_tool_descriptions()` 从 `ToolRegistry` 动态生成工具描述:
- 遍历工具名列表,从注册中心获取每个工具的 description 和 input_schema
- 生成: 工具名 - 描述, When to use, Parameters, Returns
- 新增/修改工具后自动更新prompt,无需人工维护模板

### 2.6 各分类 Prompt 类差异

| 分类 | Prompt类 | 自定义内容 |
|------|---------|-----------|
| File | FileOperationPrompts | P17互斥参数规则, write_text_file text规则, 详细工具Examples |
| System | SystemPrompts | FUND_RUNTIME基础运行时工具, Registry安全警告 |
| Network | NetworkPrompts | http_request示例, URL处理规则 |
| Document | DocumentPrompts | 文档处理工具 |
| Desktop | DesktopPrompts | 屏幕交互工具 |

所有分类共享: OUTPUT_FORMAT, TOOL_CALL_RULES, get_rollback_instructions, 避免重复规则。

---

## 3. Message 构建与 conversation_history 管理

### 3.1 MessageBuilder — 唯一状态管理器

`app/services/agent/message_builder.py` 是 conversation_history 的唯一管理入口。

**核心属性:**
- `conversation_history: List[Dict]` — 正式对话历史
- `temp_history: List[Dict]` — 临时历史(chunk缓存), 字符上限50000

**生命周期绑定:** MessageBuilder 实例必须与 Agent 实例强绑定,严禁全局共享单例。

### 3.2 conversation_history 操作入口

| 方法 | 职责 | 数据格式 |
|------|------|---------|
| `init_history(sys_prompt, task_prompt)` | 初始化: 注入system+user | `[{"role":"system",...}, {"role":"user",...}]` |
| `add_assistant(content)` | 追加AI回复 | `{"role":"assistant", "content": "..."}` |
| `add_observation(obs_text, llm_call_count, fc_context)` | 追加工具结果 | 双模式(见下) |
| `add_parse_error(error_msg)` | 追加解析错误 | 特殊observation |
| `flush_temp_to_history(chunk_buffer)` | 从temp刷入正式 | 转为assistant消息 |

**add_observation 双模式:**
- **FC协议模式** (有fc_context): 注入 `assistant(tool_calls)` + `tool(tool_call_id)` — 符合OpenAI Function Calling协议
- **Text模式** (无fc_context): 注入 `user` + `"[Tool Result]\n..."` — 纯文本工具结果

### 3.3 prepare_messages_for_llm — 组装发给LLM的消息列表

```python
messages = list(self.conversation_history)
if self.temp_history:
    messages = messages + list(self.temp_history)
return messages
```

然后由 `UniversalAgent._call_llm()` 在返回前追加:
- `_build_executed_tool_summary()` — 已执行工具汇总提示 ("【已执行工具(勿重复)】...")

### 3.4 trim_history — 容量感知裁剪

**触发条件:** 总字符数 > MAX_CONTEXT_CHARS * 0.8 (120,000字符,MAX=150,000)

**裁剪策略:**
1. 分类消息为: system / observation / assistant 三组
2. observation去重 (基于MD5指纹, FC协议的role:tool不参与去重)
3. assistant保留最新10条
4. observation保留最新30条
5. observation从最旧开始截断,直到总字符 < MAX_CONTEXT_CHARS * 0.7 (105,000)
6. 重组: system + trimmed_obs + assistant_msgs
7. FC配对完整性校验 (确保assistant(tool_calls)和tool(tool_call_id)配对)
8. 极端保护: 如果结果<2条且原历史>10条,直接取前2+后8条

### 3.5 Observation 预算衰减

`OBSERVATION_BUDGET = min(OBSERVATION_BUDGET_MIN + DECAY * max(0, 5 - llm_call_count), MAX)`

即:
- LLM调用1次: 20000 + 10000*4 = 60000, 上限50000
- LLM调用5次: 20000 + 10000*0 = 20000
- LLM调用>5次: 20000

随着对话轮次增加,observation可容纳内容逐渐减少。

---

## 4. Agent ReAct 循环与消息流

### 4.1 完整入口链路

```
API: POST /chat/stream
  → chat_router.py (路由分发)
  → chat_stream_v2.py (API层入口)
    → detect_intent() (意图检测: 文件/系统/网络/文档/桌面)
    → get_service() (获取LLM客户端 BaseAIService)
    → register_task() (任务注册)
    → step_start() (发送StartStep SSE事件)
    → run_sse_stream() (SSE流运行器)
      → AgentFactory.create() (创建Agent实例)
      → agent.run_react_cycle() (ReAct循环, async generator)
        → _initialize_run_state() (初始化: 重置history, 构建sys_prompt+task_prompt, 注入init_history)
        → while step_counter < max_steps:
            → _process_single_step() (单次循环)
              → agent._call_llm() (调用LLM, 流式)
              → parse_llm_response() (解析LLM响应)
              → handler dispatch (根据type分发)
            → 检查结果, 决定是否继续
      → finally: save_execution_steps_to_db() (批量保存一次)
  → StreamingResponse (SSE输出到客户端)
```

### 4.2 ReAct 循环核心 (react_cycle.py)

**薄调度模式:** `react_cycle.py` 只负责循环调度+类型分派,不含业务逻辑。业务逻辑在 `handlers/` 目录。

**消息分发注册表:**
```
"action"    → handle_action      (LLM要调用工具)
"answer"    → handle_answer      (LLM直接回答/完成任务)
"implicit"  → handle_answer      (LLM隐式回答)
"chunk"     → handle_chunk       (LLM部分响应, 可累积)
"parse_error" → handle_parse_error (LLM返回非JSON文本)
_default    → handle_unknown     (未知类型)
```

### 4.3 _process_single_step 详细流程

```
1. step_counter++
2. agent._call_llm() — 流式获取LLM响应
   - 每个chunk: yield ("chunk", ChunkStep)
   - 完整响应: yield ("response", full_content)
3. 解析: parsed = parse_llm_response(llm_response)
4. 提取reasoning: 如有, yield ChunkStep(is_reasoning=True)
5. 类型分发: handler = _TYPE_HANDLERS[parsed.type]
6. handler执行 (action/answer/chunk/parse_error/unknown)
7. 工具提醒 (仅chunk类型且无工具调用时):
   → conversation_history.append({"role":"system", "content": _TOOL_REMINDER})
```

### 4.4 ActionHandler 详细流程

1. **安全检查+HITL确认:** 遍历所有待调用工具,检查安全规则,需要确认时yield IncidentStep并等待用户审批
2. **工具执行:** 并行(多工具)或串行(单工具)执行
3. **构建Observation:**
   - 对每个工具: yield ActionToolStep (带execution_result)
   - 构建observation文本 → yield ObservationStep
   - 更新message_builder (add_observation)
   - 追加assistant消息 (add_assistant)

### 4.5 parse_llm_response 解析链

```
handle_dict_input → dict直接处理
handle_list_input → list处理
handle_json_array_string → JSON数组字符串
handle_empty_input → 空输入→parse_error
handle_standard_json → 标准JSON→type/action/answer
handle_mixed_text_json → 混合文本(前缀+JSON)→action/finish/implicit
```

解析结果 type 决定下游handler:
- `"action"` → LLM要调用工具, 含tool_name和tool_params
- `"answer"` → tool_name="finish", LLM完成任务
- `"implicit"` → LLM有content/reasoning但无tool_name
- `"chunk"` → LLM部分响应, 未解析为完整action
- `"parse_error"` → 解析失败

---

## 5. LLM 客户端调用

### 5.1 BaseAIService 两层结构

```
BaseAIService (llm_core.py) — 业务层
  └── create_llm_client() → SDK实例 (client_sdk.py) — HTTP层
```

**BaseAIService 三个核心接口:**
- `request(messages, mode, tools, tool_choice)` — 非流式请求
- `request_stream(messages, mode, tools, tool_choice)` — 流式请求 (SSE)
- `chat(message, history)` — 便捷对话方法

**mode参数:**
- `"text"` — 纯文本对话
- `"tools"` — Function Calling模式, 附带tools定义

### 5.2 UniversalAgent._call_llm() — 消息准备与模式选择

```python
async def _call_llm(self):
    self.llm_call_count += 1
    self.message_builder.trim_history()           # 裁剪历史
    
    messages = self.message_builder.prepare_messages_for_llm()  # 获取消息列表
    
    executed_summary = self._build_executed_tool_summary()
    if executed_summary:
        messages.append({"role": "system", "content": executed_summary})  # 追加已执行工具汇总
    
    openai_tools = self._get_openai_tools()       # 获取OpenAI格式工具定义
    
    if openai_tools:
        yield from self._call_llm_fc_stream(messages, openai_tools)   # FC模式
    else:
        yield from self._call_llm_text_stream(messages)               # Text模式
```

### 5.3 FC模式 vs Text模式

**FC模式 (_call_llm_fc_stream):**
- 使用 `mode="tools"`, 传递 `tools=openai_tools`, `tool_choice="auto"`
- LLM返回结构化的tool_calls
- 流式聚合tool_calls (跨chunk拼接function name和arguments)
- 流结束后如有聚合tool_calls, 转换为JSON content注入
- FC失败时降级到text模式

**Text模式 (_call_llm_text_stream):**
- 使用 `mode="text"`, 不传递tools
- LLM返回纯文本 (JSON格式, 需手动解析)
- 降级路径: 流失败→非流式text→空字符串兜底

### 5.4 工具定义生成

`tool_registry.to_openai_tools(category)` → 从注册中心获取所有工具 → 转换为OpenAI Function Calling格式 (name, description, parameters JSON Schema)。TTL缓存 (300秒), 支持 `invalidate_tool_cache()` 清除。

### 5.5 LLM 重试机制

`BaseAIService.request_stream()` 内置重试:
- 最大重试3次
- 退避策略: 2^retry_count 秒
- 可重试状态码: 429, 500, 502, 503, 504
- 可重试连接错误: ConnectError, ReadError, WriteError

---

## 6. 工具结果到 Observation 的转换

### 6.1 三层架构

```
工具层 (_response.py)
  → build_success / build_error / build_warning
     ↓
Agent层 (tool_result_factory.py)
  → create_tool_result / create_error_tool_result / create_warning_tool_result
     (追加error_type, metadata等Agent特有字段)
     ↓
格式化层 (observation_formatter.py)
  → format_llm_observation() — 给LLM看的observation文本
  → extract_status() — 提取status字段
```

### 6.2 工具返回统一结构

必填字段: code, data, message
可选字段: warning, llm_data, next_actions, retry_count, return_direct, attachment

- **SUCCESS**: code="SUCCESS"
- **WARNING_***: code以"WARNING_"开头, Agent视为成功但有风险
- **ERR_***: code以"ERR_"开头或其他, 视为失败

### 6.3 format_llm_observation 格式化规则

**成功结果:**
```
Observation: success - [message]
[⚠ 警告: warning_text]  (如有)
数据: [json.dumps(llm_data或data, safe_limit=100000)]
推荐下一步操作: [next_actions]  (如有)
```

**警告结果:**
```
Observation: warning - [message]
部分数据: [json]  (如有)
推荐下一步操作: [next_actions]
```

**错误结果:**
```
Observation: error [code] - [message]
[替代建议]  (从tool_registry获取失败提示)
推荐下一步操作: [next_actions]
```

---

## 7. DB 持久化: Execution Steps 存储

### 7.1 存储时机与方式

**唯一保存入口:** `chat_stream.save_execution_steps_to_db()`
- 在 `run_sse_stream()` 的 finally 块中调用
- 正常完成、异常、取消——统一走这里
- 每次事件 append 到 `current_execution_steps` 列表
- 最终 **批量保存一次**, 不再每个chunk全量save

### 7.2 存储结构

`ExecutionStepsUpdate`:
- `execution_steps`: list of dict — 执行步骤详情 (Step.to_dict())
- `content`: str — AI生成的最终文本内容
- `reply_to_message_id`: int — 回复的用户消息ID

### 7.3 Step 模型体系

10个Step类, 全部继承 `ReasoningStep` 抽象基类:

| Step类 | type值 | 用途 |
|--------|--------|------|
| StartStep | "start" | 任务开始 |
| ChunkStep | "chunk" | 流式文本块(实时输出) |
| ThoughtStep | "thought" | 推理思考 |
| ActionToolStep | "action" | 工具调用 |
| ObservationStep | "observation" | 工具执行结果 |
| FinalStep | "final" | 任务完成 |
| ErrorStep | "error" | 错误 |
| IncidentStep | "incident" | HITL审批中断 |
| ReasoningStep | (抽象基类) | — |

所有Step统一 `to_dict()` 方法: `{"type": ..., "step": ..., "timestamp": ..., "content": ..., ..._extra_fields}`

### 7.4 DB Message模型

```python
class Message(BaseModel):
    id: Optional[int]
    session_id: str
    role: str            # user / assistant / system
    content: str
    timestamp: str
    execution_steps: Optional[str]  # JSON字符串
```

SSE流产生的所有Step合并为一个assistant消息的 `execution_steps` 字段 (JSON数组字符串) 存入DB。

---

## 8. Prompt 日志系统

`PromptLogger` 使用线程局部存储 (threading.local), 每个请求一个独立JSON日志文件。

**记录内容:**
- 基本信息: 时间戳、会话ID、用户消息ID、AI消息ID、用户消息
- Prompt组装过程: 系统Prompt生成、中间层注入、任务Prompt、工具Prompt、观察结果Prompt
- LLM调用记录: 轮次、调用类型(text/tools)、模型、提供商、消息统计、消息摘要(截断200)、完整消息列表
- LLM返回: 轮次、返回类型、返回内容(截断2000)、结束原因

**日志文件:** `backend/logs/prompt-logs/prompt_{message_id}_{timestamp}.json`

**注意:** PromptLogger在 `FileOperationPrompts.get_system_prompt()` 中被调用, 记录中间层注入的服务器OS信息。

---

## 9. 完整消息流图

### 9.1 请求进入 → LLM调用 → SSE返回 全链路

```
[用户] ──POST /chat/stream──→ [FastAPI]
                                  │
                                  ├─ detect_intent(user_input) → intent_type (file/system/...)
                                  ├─ get_service() → BaseAIService (LLM客户端)
                                  ├─ register_task(task_id, ai_service)
                                  ├─ step_start() → 发送 StartStep SSE
                                  │
                                  └─ [run_sse_stream]
                                        │
                                        ├─ AgentFactory.create(intent_type) → UniversalAgent
                                        │   ├─ resolve_agent_config() → AgentConfig
                                        │   ├─ config.prompt_class() → Prompt类实例 (如FileOperationPrompts)
                                        │   └─ init: MessageBuilder, ToolManager, StepEmitter
                                        │
                                        ├─ run_react_cycle(task, task_id)
                                        │   │
                                        │   ├─ _initialize_run_state(task)
                                        │   │   ├─ message_builder.reset_per_run()
                                        │   │   ├─ _get_system_prompt() → prompts.build_full_system_prompt()
                                        │   │   │   ├─ ① get_system_prompt() (分类特有)
                                        │   │   │   ├─ ② OUTPUT_FORMAT
                                        │   │   │   ├─ ③ TOOL_CALL_RULES
                                        │   │   │   ├─ ④ get_safety_reminder()
                                        │   │   │   ├─ ⑤ get_rollback_instructions()
                                        │   │   │   ├─ ⑥ 避免重复规则
                                        │   │   │   └─ \n\n.join()
                                        │   │   ├─ _build_candidates_hint()
                                        │   │   ├─ _build_cross_tool_hint()
                                        │   │   ├─ sys_prompt = [8个部分.join]
                                        │   │   ├─ _get_task_prompt(task) → prompts.get_task_prompt(task)
                                        │   │   └─ message_builder.init_history(sys_prompt, task_prompt)
                                        │   │       └→ conversation_history = [
                                        │   │              {"role":"system", "content": sys_prompt},
                                        │   │              {"role":"user", "content": task_prompt}
                                        │   │           ]
                                        │   │
                                        │   ├─ while step_counter < max_steps:
                                        │   │   │
                                        │   │   ├─ _process_single_step()
                                        │   │   │   │
                                        │   │   │   ├─ agent._call_llm()
                                        │   │   │   │   ├─ llm_call_count++
                                        │   │   │   │   ├─ trim_history() (容量裁剪)
                                        │   │   │   │   ├─ messages = prepare_messages_for_llm()
                                        │   │   │   │   │   ├─ messages = conversation_history + temp_history
                                        │   │   │   │   │   └─ _cap_temp_history() (50000字符限制)
                                        │   │   │   │   ├─ executed_summary = _build_executed_tool_summary()
                                        │   │   │   │   │   └─ "【已执行工具(勿重复)】tool1→success|data; tool2→success..."
                                        │   │   │   │   ├─ openai_tools = _get_openai_tools()
                                        │   │   │   │   ├─ FC模式: request_stream(messages, mode="tools", tools=openai_tools)
                                        │   │   │   │   │   └─ BaseAIService.request_stream() → SDK SSE解析
                                        │   │   │   │   └─ Text模式: request_stream(messages, mode="text")
                                        │   │   │   │       └─ 降级: FC失败→text; text失败→非流式→空串
                                        │   │   │   │
                                        │   │   │   ├─ parsed = parse_llm_response(llm_response)
                                        │   │   │   │   └→ {type: "action"/"answer"/"chunk"/"parse_error", ...}
                                        │   │   │   │
                                        │   │   │   ├─ handler.dispatch(parsed.type)
                                        │   │   │   │   ├─ action → ActionHandler
                                        │   │   │   │   │   ├─ check_safety_and_confirm() → HITL等待
                                        │   │   │   │   │   ├─ execute_tools() → 并行/串行
                                        │   │   │   │   │   │   └→ ToolRetryEngine.execute_tool_with_retry()
                                        │   │   │   │   │   │       ├─ 参数验证 → 非法→报错
                                        │   │   │   │   │   │       ├─ 重试引擎 (指数退避, 最多3次)
                                        │   │   │   │   │   │       └─ 同步工具: to_thread包装
                                        │   │   │   │   │   ├─ build_observation()
                                        │   │   │   │   │   │   ├─ format_llm_observation() → observation文本
                                        │   │   │   │   │   │   ├─ message_builder.add_observation()
                                        │   │   │   │   │   │   │   └→ conversation_history.append(tool/user消息)
                                        │   │   │   │   │   │   ├─ message_builder.add_assistant()
                                        │   │   │   │   │   │   │   └→ conversation_history.append(assistant消息)
                                        │   │   │   │   │   │   └─ yield ActionToolStep + ObservationStep
                                        │   │   │   │   │
                                        │   │   │   │   ├─ answer → 直接yield FinalStep, agent.status=COMPLETED
                                        │   │   │   │   ├─ chunk → 累积到chunk_buffer, 可能提升为implicit/answer
                                        │   │   │   │   ├─ parse_error → 有内容→answer完成, 无内容→error失败
                                        │   │   │   │   └─ unknown → error失败
                                        │   │   │   │
                                        │   │   │   └─ 工具提醒 (仅chunk类型且无工具调用):
                                        │   │   │       └→ conversation_history.append({"role":"system", "content": _TOOL_REMINDER})
                                        │   │   │
                                        │   │   └─ 检查agent.status, chunk_buffer, 决定是否继续
                                        │   │
                                        │   └─ _on_after_loop() + _complete_tracked_task()
                                        │
                                        └─ finally: save_execution_steps_to_db(session_id, execution_steps, content)
                                           └→ 批量写入DB, 每个Step.to_dict()合并到assistant消息
                                           └→ execution_steps JSON数组字符串
                                           └→ content作为message.content
                                           └→ 每个Step事件也作为SSE逐条yield

[SSE] ← StreamingResponse ← 逐条yield SSE事件
```

### 9.2 conversation_history 生命周期

```
初始化 (init_history):
  [{"role":"system", "content": <15KB+系统Prompt>},
   {"role":"user", "content": <Task+时间+步骤>}]

ReAct循环每次迭代:
  - add_observation() → [assistant(tool_calls), tool(result)] 或 [user("[Tool Result]...")]
  - add_assistant()   → [assistant("text")]

每轮LLM调用前:
  - trim_history() (容量>80%时裁剪)
  - prepare_messages_for_llm() → conversation_history + temp_history
  - 追加 executed_tool_summary (system消息)

发送前最终消息列表:
  [system, user, assistant, tool_result, assistant, tool_result, ..., assistant, system(summary)]
```

---

## 10. 不合理之处分析

### 10.1 严重问题

**S1: conversation_history 与 message_builder 存在引用别名问题**

`initialize_run_state.py` 第21行和第32行:
```python
self.conversation_history = self.message_builder.conversation_history
```
这将 `agent.conversation_history` 设置为与 `message_builder.conversation_history` 相同的列表引用。这意味着:
- 对 `agent.conversation_history` 的直接操作 (如 `react_cycle.py` L102) 会影响 `message_builder`
- 但后续如果重新赋值 `self.message_builder.conversation_history = [...]` (init_history), `agent.conversation_history` 不会同步
- 这种"有时别名、有时分离"的行为容易引发状态不同步Bug

**建议:** 统一通过 `message_builder` 操作, 删除 `self.conversation_history = message_builder.conversation_history` 的别名赋值, 或者始终维护别名。

**S2: system prompt 过大, 每个工具都重复注入**

系统Prompt包含: 系统信息(几百字) + 工具描述(每个工具~200字×~20个工具≈4KB) + OUTPUT_FORMAT(~2KB) + TOOL_CALL_RULES(~1KB) + 安全提醒(~500字) + 回滚说明(~300字) + 避免重复规则(~300字) + 候选意图提示 + 跨分类工具提示 = 总计可达 8-15KB。

这还没算上 conversation_history 中累积的 observation。当对话轮次多时, 单轮发送给LLM的tokens量可能轻松超过 50KB。

**建议:** 考虑对工具描述做压缩 (如缩短描述文本), 或只在首次调用时注入, 后续轮次用轻量引用。

**S3: FC模式和Text模式的消息结构不一致**

- FC模式: assistant消息可以有 `content=None` + `tool_calls=[...]`, 然后 `role:tool` 消息
- Text模式: 纯文本JSON, 没有 `tool_calls` 字段

当 `trim_history()` 处理时, `_total_chars()` 方法正确判断了 `content is None` 的情况, 但 `_classify_messages()` 只识别 `role=="assistant"` 和 `_is_observation_role()`, 没有区分FC模式和Text模式的assistant消息格式。

**建议:** 统一两种模式的message结构, 或在裁剪逻辑中明确处理FC协议消息。

### 10.2 中等问题

**M1: 工具提醒注入使用 hardcoded text, 与OUTPUT_FORMAT不一致**

`react_cycle.py` L36-43的 `_TOOL_REMINDER` 是硬编码的纯文本提醒:
```
【系统提示·工具调用提醒】\n你刚才的回复没有调用任何工具...
```

这与 `BasePrompts.OUTPUT_FORMAT` 的强制工具调用规则有重复, 且格式不同 (一个是Markdown文本, 一个是JSON规范)。

**建议:** 删除硬编码提醒, 统一在OUTPUT_FORMAT/TOOL_CALL_RULES中处理。

**M2: Observation文本没有长度上限保护**

`add_observation()` 调用 `_prepare_observation_text()` 做截断, 但budget计算基于 `llm_call_count`:
- 第1次调用: budget=50000, 但observation文本通常远小于此
- 第5次调用: budget=20000
- 第10次调用: budget=20000 (不再衰减)

单个observation可能超过budget, 此时截断。但截断后observation仍然可能占用大量tokens。

**建议:** 对单个observation做更激进的截断 (如限制为5000字符)。

**M3: PromptLogger 记录完整消息列表但没实际使用**

`prompt_logger.log_llm_call()` 记录 `完整消息列表: messages`, 但:
- 每条消息内容被截断为200字符
- 文件路径在 `backend/logs/prompt-logs/` 但代码中没有读取/消费这些日志的逻辑
- 线程局部存储在多线程/异步场景下可能有问题 (asyncio.Task可能在同一线程执行)

**建议:** 要么删除冗余记录, 要么实现日志消费/分析面板。

**M4: temp_history 和 conversation_history 的关系不清晰**

`temp_history` 在 `chunk_handler` 中被使用, chunk_buffer.append(content), 然后 `flush_temp_to_history()` 将temp刷入正式history。但 `add_assistant()` 直接追加到 `conversation_history`, 不走temp。

这意味着:
- chunk累积的内容走 temp → flush → conversation_history
- 工具执行结果的assistant消息走 conversation_history 直接追加

这两种路径在 `prepare_messages_for_llm()` 中被合并, 但它们的语义不同 (一个是未完成的输出, 一个是已确认的输出)。

**建议:** 文档中明确两种路径的触发条件和使用场景。

### 10.3 轻微问题

**L1: 工具描述生成在每次build_full_system_prompt时被调用, 但结果没缓存**

`BasePrompts.build_tool_descriptions()` 每次从 `tool_registry` 查询工具, 而prompt模板在Agent初始化时只创建一次。问题不大, 但如果工具注册表频繁变化可能有影响。

**L2: `_extract_display_data` 回退到 `data` 而不是 `llm_data`**

`observation_formatter.py` L122:
```python
display_data = result.get("llm_data") or result.get("data")
```
`llm_data` 本意是给LLM的精简数据, 如果没有llm_data则回退到完整data。这个逻辑正确, 但 `or` 操作符在data为空字符串时会回退到data, 可能不是预期行为 (空字符串vs None)。

**L3: 工具重试引擎和LLM客户端重试引擎双重独立**

- `ToolRetryEngine`: 工具执行重试 (工具调用失败时)
- `BaseAIService.request_stream()`: LLM API调用重试 (HTTP级别)

两层重试机制独立运作, 但都使用 `RetryEngine` 类。代码重复度可以更低。

**L4: chat_stream_v2 和 run_sse_stream 中的 cancel/check 逻辑分散**

取消检查和暂停检查分散在 `chat_stream_v2.py` 和 `run_sse_stream.py` 中, 每个SSE yield处都要检查。可以考虑统一集成到SSE流中。

---

## 11. 总结

### 11.1 核心数据流

1. **Prompt组装:** 声明式配置 → Prompt类 → build_full_system_prompt() → 8个部分组成
2. **Message构建:** init_history() → ReAct循环中的add_assistant()/add_observation() → prepare_messages_for_llm()
3. **LLM调用:** trim_history() → 组装messages → FC或Text模式 → 流式输出
4. **结果处理:** parse_llm_response() → handler分发 → 工具执行/完成
5. **Observation转换:** 工具结果 → format_llm_observation() → observation文本 → 追加到conversation_history
6. **SSE输出:** Step事件 → to_dict() → format_agent_sse() → StreamingResponse
7. **DB持久化:** 所有Step to_dict() → 批量保存 → assistant消息(execution_steps JSON + content)

### 11.2 关键设计特点

- **声明式配置驱动:** Agent类型由AGENT_REGISTRY决定, 无硬编码分支
- **SRP拆分:** Prompt模板、消息构建、LLM调用、工具管理各自独立
- **双模式LLM调用:** FC (结构化) + Text (灵活), 自动降级
- **流式优先:** 所有LLM调用默认流式, chunk实时输出
- **容量控制:** observation预算衰减 + history裁剪 + temp_history限制
- **线程安全:** PromptLogger使用threading.local

### 11.3 需要改进的要点

1. **修复conversation_history别名问题** (S1) — 最高优先级
2. **精简System Prompt** (S2) — 工具描述压缩
3. **统一FC/Text模式的消息处理** (S3) — 裁剪逻辑一致性
4. **删除硬编码工具提醒** (M1) — 与OUTPUT_FORMAT统一
5. **精简Observation截断** (M2) — 防止单条observation过大
