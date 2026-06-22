# Agent-工具-意图 全系统深度分析报告

> 分析范围: G:\OmniAgentAs-desk\backend\app\ (约300个Python文件，核心分析28个)
> 复查次数: 5遍逐代码验证
> 分析日期: 2026-06-13
> 关键架构变更: FC-only重构 + tool_search动态加载 + 删除CRSS意图系统

---

## 一、系统架构全景图

### 1.1 当前架构（FC-only + UniversalAgent + tool_search）

```
API层 (FastAPI)
├── chat_router.py            路由定义 POST /chat/stream
├── chat_stream_v2.py         API入口(95行): register_task → interrupt → step_start → run_sse_stream
├── models.py                 ChatRequest模型(messages/stream/session_id)
├── step_start.py             Start步骤发射(25行)
├── confirm_operation.py      HITL人工确认(118行): asyncio.Future机制
└── validate_chat_config.py   配置校验(40行)

SSE流运行器
├── run_sse_stream.py         SSE流运行器(125行): 创建Agent → run_react_cycle → 格式化SSE → DB保存

Agent层 (核心循环)
├── universal_agent.py        通用Agent(241行): 初始仅加载FUND_RUNTIME，tool_search动态注入
├── agent_factory.py          工厂(23行): create_agent(llm_client, task_id)
├── base_agent.py             Agent基类(80行): SRP骨架，组合AgentInitializer/ToolManager/StepEmitter/RetryEngine
├── react_cycle.py            ReAct循环核心(125行): 薄调度+注册式分派(action/answer)
├── message_builder.py        消息构建器(308行): FC协议conversation_history管理
├── tool_retry_engine.py      工具重试引擎(238行): 参数验证+重试+统一错误
├── observation_formatter.py  observation格式化(222行): 工具结果→LLM文本
├── chunk_buffer.py           chunk缓冲器(70行): 阈值检测+强制停止

Handler层 (业务逻辑)
├── action_handler.py         action处理(208行): 安全校验→工具执行→FC协议observation
└── answer_handler.py         answer处理(41行): ThoughtStep + FinalStep

初始化层
├── initialize_run_state.py   运行状态初始化(31行): 重置steps/message_builder/inject system prompt
├── agent_initializer.py      Agent初始化(66行): LLM/状态/消息/Task追踪
├── tool_manager.py           工具管理器(48行): 初始加载meta+FUND_RUNTIME
└── step_emitter.py           步骤发射器(60行): 记录steps + Task追踪

Step类型层 (steps/)
├── base.py                   ReasoningStep(ABC) 抽象基类
├── start_step.py             StartStep type="start" is_done=True
├── thought_step.py           ThoughtStep type="thought"
├── action_step.py            ActionToolStep type="action_tool"
├── observation_step.py       ObservationStep type="observation"
├── chunk_step.py             ChunkStep type="chunk"
├── final_step.py             FinalStep type="final" is_done=True
├── error_step.py             ErrorStep type="error" is_done=True
└── incident_step.py          IncidentStep type="incident"

Prompt层
├── base_prompt_template.py   基类(115行): build_full_system_prompt() 4步组装
├── system_adapter.py         系统信息适配器(184行): OS/路径/命令/Git/时间
├── system_prompts.py         SystemPrompts(26行): 角色定义+业务规则
└── project_context.py        项目上下文(54行): 读取OmniAgent.md

工具层
├── registry.py               ToolRegistry(290行): 注册/过滤/to_openai_tools
├── tool_types.py             ToolCategory(6类)+ToolMetadata+ToolSafetyLevel(5级)
├── tool_constants.py         工具常量(179行): CATEGORY_MODULES/超时/重试配置
├── tool_description.py       Schema→OpenAI转换(118行)
├── tool_safety_checker.py    安全检查器(164行): Layer 2安全级别+Layer 3已知风险
├── lazy_loader.py            懒加载器(80行): ensure_tools_registered()
├── schema_utils.py           Schema工具(86行): 修复Pydantic V2 type缺失
└── 各分类注册: file(10工具) shell(4) network(6) system(9) desktop(6) document(9) meta(6) = 50个工具

SSE/DB层
├── chat_stream.py            SSE格式+DB保存(197行): format_agent_sse/save_execution_steps_to_db
├── save_execution_steps.py   DB保存入口(41行): conversation持久化
└── stream_parser.py          流式解析器(30行): create_cancelled_chunk/create_error_chunk

类型/工具层
├── agent_types/              AgentStatus(5种) + AgentResult
├── agent_utils/              fc_message_types/message_utils/tool_result_factory
└── llm/                      LLMClient(154行) + StreamChunk + model_adapters
```

### 1.2 关键文件统计

| 文件 | 行数 | 作用 | 重要度 |
|------|------|------|--------|
| universal_agent.py | 241 | 通用Agent核心: tool_search+FC-only LLM调用 | ★★★★★ |
| message_builder.py | 308 | FC协议conversation_history管理 | ★★★★★ |
| react_cycle.py | 125 | ReAct循环薄调度: 循环+分派 | ★★★★☆ |
| action_handler.py | 208 | action处理: 安全校验+工具执行+observation | ★★★★☆ |
| tool_retry_engine.py | 238 | 工具重试引擎: 参数验证+重试+错误处理 | ★★★★☆ |
| tool_safety_checker.py | 164 | 工具安全检查: 安全级别+已知风险+HITL | ★★★★☆ |
| registry.py | 290 | 工具注册表: 注册/过滤/OpenAI格式转换 | ★★★★☆ |
| run_sse_stream.py | 125 | SSE流运行器: Agent创建+事件流+DB保存 | ★★★★☆ |
| base_agent.py | 80 | Agent基类: SRP骨架+生命周期Hook | ★★★☆☆ |
| observation_formatter.py | 222 | observation格式化: 工具结果→LLM文本 | ★★★☆☆ |
| chat_stream_v2.py | 95 | API入口: Task生命周期管理 | ★★★☆☆ |
| chat_stream.py | 197 | SSE格式化+DB保存+错误响应 | ★★★☆☆ |
| base_prompt_template.py | 115 | Prompt基类: 4步组装框架 | ★★★☆☆ |
| tool_types.py | 129 | ToolCategory(6类)+ToolSafetyLevel(5级)+ToolMetadata | ★★★☆☆ |
| chunk_buffer.py | 70 | chunk阈值检测+强制停止 | ★★☆☆☆ |
| step_emitter.py | 60 | Step发射+Task追踪 | ★★☆☆☆ |
| agent_initializer.py | 66 | Agent初始化(LLM/状态/消息/Task追踪) | ★★☆☆☆ |
| tool_manager.py | 48 | 工具加载管理器 | ★★☆☆☆ |
| answer_handler.py | 41 | answer处理: FinalStep | ★★☆☆☆ |

### 1.3 核心架构特征

| 特征 | 说明 |
|------|------|
| **FC-only模式** | LLM返回tool_calls原生消费，不经过JSON roundtrip |
| **tool_search动态加载** | 初始仅加载FUND_RUNTIME，其余通过tool_search按需注入 |
| **无CRSS意图系统** | 不存在crss_scorer/intent_mapper/AGENT_REGISTRY |
| **单一UniversalAgent** | 不存在分类Agent(file/system/network等)，统一由UniversalAgent处理 |
| **薄调度模式** | react_cycle.py仅~120行，业务逻辑100%在handlers |
| **SRP拆分彻底** | ToolManager/StepEmitter/RetryEngine/ChunkBuffer各自独立 |

---

## 二、完整执行链路: API入口到LLM

### 2.1 入口链 (逐行验证)

```
用户输入 → chat_router.py (POST /chat/stream)
  │
  └─ chat_stream_v2(request)                    [chat_stream_v2.py L38]
     │
     ├─ L46: user_input = request.messages[-1].content
     ├─ L47: ai_service = get_service()
     ├─ L48: session_id = request.session_id or str(uuid.uuid4())
     │
     └─ L50: async def generate():
        │
        ├─ L52-53: task_id = str(uuid.uuid4())
        │           _current_task_id.set(task_id)
        ├─ L54: next_step = create_step_counter()
        ├─ L55-56: execution_steps = []; state = StreamState()
        │
        ├─ L59: await register_task(task_id, ai_service)
        │
        ├─ L61-65: task_interrupt_check → 如果已中断则返回
        │
        ├─ L67-68: step_start(...) → yield StartStep (SSE)
        │
        ├─ L70-87: async for sse_chunk in run_sse_stream(...):
        │   ├─ L78-79: task_pause_check_and_yield
        │   ├─ L81-86: task_cancel_check_and_yield
        │   └─ L87: yield sse_chunk
        │
        └─ L93: finally: await task_cleanup(task_id, state.llm_call_count)
```

### 2.2 AgentFactory.create 链路 (当前版本)

```
run_sse_stream()
  ↓ [run_sse_stream.py L37-39]
agent = create_agent(llm_client=llm_client, task_id=task_id)
  ↓ [agent_factory.py L11-22]
UniversalAgent(llm_client=llm_client, task_id=task_id)
  ↓ [universal_agent.py L37-61]
BaseAgent.__init__()
  ├─ AgentInitializer._init_llm(self, llm_client)        设置LLM客户端
  ├─ AgentInitializer._init_state(self, task_id, max_steps)
  ├─ AgentInitializer._init_messages(self)                创建MessageBuilder
  ├─ ToolManager.__init__(self) → init_tools()
  │     └─ 始终加载 meta 工具 + FUND_RUNTIME 分类
  ├─ ToolRetryEngine(self._tools_dict)                    创建重试引擎
  ├─ AgentInitializer._init_task_tracking(self)           创建任务追踪
  └─ StepEmitter(self)                                    创建步骤发射器
```

### 2.3 _get_system_prompt 链路 (当前版本)

```
UniversalAgent._get_system_prompt()     [universal_agent.py L71-74]
  └─ return self.prompts.build_full_system_prompt()
     ↓ [system_prompts.py → base_prompt_template.py L92-110]
BasePrompts.build_full_system_prompt()
  ├─ ① _get_system_info()              系统信息(OS/路径/命令/Git/时间)
  │     └─ system_adapter.py: SystemAdapter生成Windows环境信息
  ├─ ② _get_project_context()          项目上下文(OmniAgent.md, 最多8000字符)
  ├─ ③ get_core_system_prompt()        角色定义+业务规则(子类实现)
  │     └─ SystemPrompts: "系统全能助手，负责命令执行、系统查询、时间操作、文件管理"
  └─ ④ TOOL_CALL_RULES                 回答要求: reasoning简短+中文回复+停止条件
```

### 2.4 工具加载与缓存 (当前版本)

```
_get_openai_tools()                       [universal_agent.py L187-200]
  ├─ TTL缓存检查 (300秒)
  │     if cached and current_time - cache_ts < cache_ttl: return cached
  │
  ├─ tool_registry.to_openai_tools(categories=self._loaded_categories)
  │     └─ tool_description.to_openai_tools()
  │        ├─ 遍历 registry._tools
  │        ├─ 过滤: meta.expose_to_llm=True
  │        ├─ 过滤: meta.category in categories
  │        └─ 生成: {"type": "function", "function": {name, description, parameters}}
  │
  └─ cache并返回

_load_tools_for_category (通过 tool_search 动态触发)
  ↓
UniversalAgent._execute_tool(tool_name="tool_search")
  ↓
_execute_tool → _retry_engine.execute_tool_with_retry("tool_search", params)
  ↓
Auto_inject_from_search(result)
  ├─ 解析tool_search返回的matches
  ├─ 新分类 → self._loaded_categories.add(cat)
  ├─ tool_manager.load_category(cat)      动态加载新分类工具
  ├─ invalidate_tool_cache()              清除openai_tools缓存
  └─ _patch_search_desc()                 更新tool_search描述
```

---

## 三、Agent初始化 → Prompt组装 → 工具加载

### 3.1 initialize_run_state (每次ReAct循环前)

```
initialize_run_state(self, task, task_id, context)  [initialize_run_state.py L15-31]
  │
  ├─ self.steps = []                          # 清空历史步骤
  ├─ self.message_builder.reset_per_run()     # 清空conversation_history + temp_history
  ├─ self.status = AgentStatus.THINKING
  ├─ self.llm_call_count = 0
  ├─ self.task_id = task_id (如果有)
  │
  ├─ self._on_session_init(task, context)     # Hook: 子类可override
  ├─ sys_prompt = self._get_system_prompt()   # ★ 组装系统提示
  ├─ self._on_before_loop(sys_prompt, task, context)  # Hook
  │
  ├─ self.message_builder.init_history(sys_prompt, task)
  │  └─ conversation_history = [
  │        SystemMessage(content=sys_prompt),
  │        UserMessage(content=task),
  │     ]
  │
  └─ return ChunkBuffer(self.max_consecutive_chunks)
```

### 3.2 _get_system_prompt 完整组装流程

```
UniversalAgent._get_system_prompt()     [universal_agent.py L71-74]
  │
  └─ self.prompts.build_full_system_prompt()
     │
     └─ BasePrompts.build_full_system_prompt()   [base_prompt_template.py L92-110]
        │
        ├─ ① _get_system_info()
        │     └─ system_adapter.get_system_prompt(include_commands=False)
        │        ├─ 根据服务器OS生成适配信息
        │        ├─ Windows: 路径格式、命令格式、工作目录
        │        └─ Git状态 + 当前时间
        │
        ├─ ② _get_project_context()
        │     └─ load_project_context() → 读取OmniAgent.md (最多8000字符)
        │
        ├─ ③ get_core_system_prompt()
        │     └─ SystemPrompts.get_core_system_prompt()
        │        └─ "你是一个系统全能助手，负责命令执行、系统查询、时间操作和文件管理"
        │
        └─ ④ TOOL_CALL_RULES
              └─ "reasoning简短(1-2句),始终用中文回复,停止条件:用户请求已完成/遇到无法解决的错误"
```

### 3.3 动态工具加载 (_auto_inject_from_search)

```
_auto_inject_from_search(result)    [universal_agent.py L85-101]
  │
  ├─ 解析tool_search返回的matches
  │  └─ llm_matches = result["llm_data"]["matches"]
  │
  ├─ 收集新分类
  │  for m in llm_matches:
  │     cat = ToolCategory(m["category"])
  │     if cat not in self._loaded_categories: new_cats.add(cat)
  │
  └─ 加载新分类
     for cat in new_cats:
        self._loaded_categories.add(cat)
        self._tool_manager.load_category(cat)    动态注册工具
     self.invalidate_tool_cache()                清除openai_tools缓存
     self._patch_search_desc()                   更新tool_search描述
```

---

## 四、ReAct循环 → LLM调用 → 响应解析

### 4.1 run_react_cycle 完整循环

```
run_react_cycle(agent, task, context, max_steps, task_id)  [react_cycle.py L74-125]
  │
  ├─ L86: chunk_buffer = initialize_run_state(agent, task, task_id, context)
  │
  ├─ L88: agent.status = AgentStatus.EXECUTING
  │
  ├─ L91: while agent.llm_call_count < max_steps:
  │  │
  │  ├─ L92: async for event in _process_single_step(agent, chunk_buffer):
  │  │  │
  │  │  └─ _process_single_step(agent, chunk_buffer)    [L35-71]
  │  │     ├─ L38-46: llm_response = None
  │  │     │  │
  │  │     │  └─ async for chunk_or_response in agent._call_llm():
  │  │     │     ├─ chunk_type == "chunk" → yield StepEmitter.emit(ChunkStep)
  │  │     │     └─ chunk_type == "response" → llm_response = chunk_data
  │  │     │
  │  │     ├─ L49-56: 验证 llm_response 有效性 (非None且为dict)
  │  │     ├─ L58-66: 检查 _cancelled → 中断事件
  │  │     ├─ L68: parsed_type = llm_response.get("type", "answer")
  │  │     ├─ L69: handler = _TYPE_HANDLERS.get(parsed_type, _DEFAULT_HANDLER)
  │  │     │  └─ _TYPE_HANDLERS = OrderedDict([("action", handle_action), ("answer", handle_answer)])
  │  │     └─ L70: async for event in handler(agent, llm_response, chunk_buffer):
  │  │            yield event
  │  │
  │  ├─ L95-96: if agent.status in (COMPLETED, FAILED): break
  │  └─ L98-101: if chunk_buffer.should_force_stop(): 强制停止
  │
  ├─ L103-108: except Exception → exit_with_error
  │
  └─ L110-125: finally
     ├─ L112-122: FAILED时补发FinalStep (仅当agent.steps非空)
     ├─ L124: agent._on_after_loop()
     └─ L125: agent._complete_tracked_task(status == COMPLETED)
```

### 4.2 _call_llm 纯FC模式 (FC-only重构后)

```
_call_llm()                       [universal_agent.py L103-115]
  │
  ├─ L105: self.llm_call_count += 1
  ├─ L106: self.message_builder.trim_history()  # 容量裁剪(80%阈值)
  │
  ├─ L108: messages = self.message_builder.prepare_messages_for_llm()
  │  ├─ _cap_temp_history()  # temp_history超50000字符从最旧截断
  │  └─ messages = conversation_history + temp_history
  │
  ├─ L109: openai_tools = self._get_openai_tools()  # TTL缓存300s
  │
  └─ L114: async for item in self._call_llm_fc_stream(messages, openai_tools)
     │
     └─ _call_llm_fc_stream(messages, openai_tools)  [L117-185]
        │
        ├─ L127-148: 流式调用 llm_client.request_stream(messages, tools, tool_choice="auto")
        │  ├─ 收到 reasoning → full_reasoning += content
        │  ├─ 收到 content → full_content += content, yield ChunkStep
        │  ├─ 收到 tool_calls → tool_calls_result = chunk.tool_calls
        │  └─ is_done → break
        │
        ├─ L148-156: 异常处理
        │  ├─ Exception → yield answer "LLM调用异常: {e}"
        │  └─ stream_error → yield answer "LLM流式错误: {error}"
        │
        ├─ L158-181: if tool_calls_result → action类型
        │  ├─ L159-163: 提取第一个tool_call → fc_context
        │  ├─ L164-170: 提取剩余tool_calls → _pending_calls (并行工具)
        │  └─ L172-180: yield ("response", {"type": "action", fc_context, _pending_calls, tool_name, tool_params, ...})
        │
        └─ L183-185: else → answer类型
           └─ yield ("response", {"type": "answer", "content": full_content or full_reasoning, "thought": ""})
```

### 4.3 handle_action 完整流程

```
handle_action(agent, parsed, chunk_buffer)  [action_handler.py L161-207]
  │
  ├─ L163-164: tool_name = parsed["tool_name"], tool_params = parsed.get("tool_params", {})
  ├─ L165: step = agent.llm_call_count
  │
  ├─ L167-168: pending_calls = parsed.get("_pending_calls", [])
  ├─ L169: fc_context = parsed.get("fc_context", {})
  ├─ L169-179: 组装 all_calls = [主调用] + _pending_calls
  ├─ L180: is_parallel = len(all_calls) > 1
  │
  ├─ L182-189: emit ThoughtStep (thought, reasoning, tool_name, tool_params)
  │
  ├─ L193-196: check_safety_and_confirm(agent, all_calls, step)
  │  │  └─ [action_handler.py L26-75] async generator
  │  ├─ 对每个call: ToolSafetyChecker.check_before_execute(tool_name, params)
  │  │  ├─ 安全开关检查 (config.yaml security.enabled)
  │  │  ├─ 获取ToolMetadata
  │  │  ├─ _get_effective_safety_level()  action级覆盖 > 工具级默认
  │  │  └─ _check_known_risks()           路径越权/写入污染/代码注入
  │  ├─ if blocked → ErrorStep + FAILED
  │  ├─ if requires_confirmation:
  │  │  ├─ create_confirmation(task_id)   创建Future
  │  │  ├─ yield IncidentStep(authorization_required)  先给前端
  │  │  └─ wait_for_confirmation_result(confirm_id, timeout=120)
  │  │     └─ if not confirmed → ErrorStep + FAILED
  │  └─ 继续下一个call
  │
  ├─ L198: results = await execute_tools(agent, all_calls, is_parallel, tool_name, tool_params)
  │  ├─ 如果 is_parallel → asyncio.gather 并行执行
  │  └─ 如果串行 → 逐个 await agent._execute_tool
  │
  └─ L200-207: build_observation(agent, all_calls, results, step, ...)
     ├─ 对每个call: build_observation_text(result, tool_name, tool_params)
     │  └─ format_llm_observation() → _format_success/warning/error_observation()
     ├─ _update_message_builder(agent, obs_text, per_call_fc)  FC协议追加
     │  └─ message_builder.add_observation(obs_text, llm_call_count, fc_context)
     │     └─ _append_observation() → AssistantMessage(tool_calls) + ToolResultMessage(tool_call_id)
     └─ emit ObservationStep (merged_obs, tool_name, execution_status, warning)
```

### 4.4 handle_answer 完整流程

```
handle_answer(agent, parsed, chunk_buffer)  [answer_handler.py L15-41]
  │
  ├─ L17: step = agent.llm_call_count
  ├─ L18: content = parsed.get("content", "")
  │
  ├─ L20-28: if not content → exit_with_error("empty_answer") + FAILED
  │
  ├─ L30-31: thought = parsed.get("thought", content), reasoning = parsed.get("reasoning", "")
  │
  ├─ L33-36: if thought → emit ThoughtStep(thought, reasoning)
  │
  └─ L38-41: emit FinalStep(step, response=content, thought=thought)
     └─ agent.status = AgentStatus.COMPLETED
```

---

## 五、工具执行 → 结果格式化 → 历史追加

### 5.1 ToolRetryEngine.execute_tool_with_retry

```
execute_tool_with_retry(action, action_input)  [tool_retry_engine.py L95-114]
  │
  ├─ L101: tool = _find_tool(action)  # 先查self._tools, 再查tool_registry
  │  └─ if None → return ERR_TOOL_NOT_FOUND
  │
  ├─ L109: params = _validate_params(action, action_input, tool)
  │  ├─ _are_params_valid()  # schema验证: 未知字段警告
  │  └─ _check_missing_params()  # 必需参数检查
  │
  └─ L114: _execute_with_retry(action, params, tool)
     ├─ max_retries, backoff_factor, retryable_errors, timeout = _get_retry_config(action)
     ├─ engine = RetryEngine(max_retries, EXPONENTIAL, backoff_factor)
     └─ while engine.attempt_count <= max_retries:
        └─ _execute_single_attempt(tool, params, timeout)
           ├─ if async → _execute_async_tool(tool, params, timeout)
           ├─ if sync → _execute_sync_tool(tool, params, timeout)  # asyncio.to_thread
           └─ on success → create_tool_result(data=result, retry_count=engine.attempt_count)
              on error → 继续重试或返回错误
```

### 5.2 ObservationFormatter 三层架构

```
format_llm_observation(result, tool_name, tool_params)  [observation_formatter.py L209-221]
  │
  ├─ code = result.get("code", SUCCESS_CODE)
  │
  ├─ if code == SUCCESS_CODE → _format_success_observation()
  │  ├─ _extract_display_data()  # 优先llm_data, 其次data
  │  ├─ _build_base_text()       # "Observation: success - {message}"
  │  ├─ _append_warning()        # 如有warning追加
  │  ├─ _append_data()           # 追加数据(防JSON OOM: limit=LLM_SAFE_LIMIT)
  │  └─ _format_next_actions()   # 追加推荐下一步
  │
  ├─ if code.startswith("WARNING_") → _format_warning_observation()
  │  ├─ _build_base_text()       # "Observation: warning - {message}"
  │  ├─ _append_data()           # 追加部分数据
  │  └─ _format_next_actions()
  │
  └─ else → _format_error_observation()
     ├─ f"Observation: error [{code}] - {message}"
     ├─ _append_hint()           # 获取失败替代建议(优先从registry, 否则按错误码)
     └─ _format_next_actions()
```

### 5.3 message_builder._append_observation (FC协议)

```
_append_observation(observation_text, fc_context)  [message_builder.py L71-89]
  │
  ├─ tool_call_id = fc_context.get("tool_call_id", "")
  ├─ tool_calls = fc_context.get("tool_calls", [])
  │
  ├─ L80-84: 检查是否已有相同tool_call_id的assistant消息(避免重复)
  │  └─ has_existing_assistant = any(role=="assistant" and tc.id==tool_call_id)
  │
  ├─ L85-88: 如果没有 → 追加AssistantMessage(tool_calls)
  │  └─ 确保FC协议: assistant(tool_calls)必须在role:tool之前
  │
  └─ L89: 始终追加 ToolResultMessage(content=observation_text, tool_call_id)
     └─ 结果: conversation_history = [..., AssistantMessage(tool_calls=[{id, function}]),
                                        ToolResultMessage(content="执行结果...", tool_call_id="tc_abc")]
```

### 5.4 message_builder 方法清单

| 方法 | 作用 | 调用方 |
|------|------|--------|
| reset_per_run() | 清空conversation_history + temp_history | initialize_run_state |
| init_history(sys_prompt, task) | 初始化 [SystemMessage, UserMessage] | initialize_run_state |
| add_observation(obs_text, llm_call_count, fc_context) | FC协议: 追加assistant(tool_calls) + tool(tool_call_id) | action_handler |
| prepare_messages_for_llm() | 合并history + temp_history | universal_agent._call_llm |
| trim_history() | 容量感知裁剪(80%阈值, FC配对完整性) | universal_agent._call_llm |
| _cap_temp_history() | temp_history 50000字符限制 | prepare_messages_for_llm |
| _trim_to_budget() | FC配对裁剪: 从最新往最旧扫描 | trim_history |
| _trim_fc_pairs() | FC协议配对完整性验证 | _rebuild_and_validate |

---

## 六、消息构建 → FC协议

### 6.1 FC协议消息格式

```
conversation_history 中的消息:
├── {role: "system", content: "系统提示..."}
├── {role: "user", content: "用户输入..."}
├── {role: "assistant", content: null, tool_calls: [{id: "tc_001", function: {name: "read_text_file", arguments: '{"path":"D:/test.txt"}'}}]}
├── {role: "tool", tool_call_id: "tc_001", content: "Observation: success - 文件内容..."}
├── {role: "assistant", content: null, tool_calls: [{id: "tc_002", function: {name: "execute_shell_command", arguments: '{...}'}}]}
├── {role: "tool", tool_call_id: "tc_002", content: "Observation: success - 执行结果..."}
└── (下一轮用户消息追加)
```

### 6.2 _classify_messages 分类逻辑

```
_classify_messages()  [message_builder.py L157-170]
  │
  ├─ 遍历 conversation_history
  ├─ role == "assistant" → assistant_msgs  (包括含tool_calls的)
  ├─ role == "tool" → obs_list  (FC-only: 只有role:tool是observation)
  └─ 其他 → system_msgs
```

### 6.3 _trim_to_budget FC配对裁剪

```
_trim_to_budget(obs_list, assistant_msgs, budget)  [message_builder.py L172-215]
  │
  ├─ L178: tool_to_assistant = {}  # tool_call_id → assistant消息
  │  └─ 遍历assistant_msgs, 提取tool_calls.id → tool_to_assistant
  │
  ├─ L184-186: 按原始顺序排列 obs+assistant
  │
  └─ L192-214: 从最后往前遍历
     ├─ msg.role == "tool" 且 tc_id in tool_to_assistant:
     │  └─ 保留 tool + 对应的 assistant (配对保留)
     ├─ 其他消息 → 保留
     └─ budget用完 → break
     kept.reverse()
```

### 6.4 _trim_fc_pairs 配对完整性检查

```
_trim_fc_pairs(messages)  [message_builder.py L258-291]
  │
  ├─ 遍历所有消息，提取 assistant_ids (assistant中的tool_call.id) 和 tool_ids (tool中的tool_call_id)
  ├─ paired_ids = assistant_ids ∩ tool_ids  # 交集: 双端都存在的
  └─ 只保留 paired_ids 中的消息:
     ├─ assistant消息: 只保留 id 在 paired_ids 中的 tool_calls
     ├─ tool消息: 只保留 tool_call_id 在 paired_ids 中的
     └─ system消息: 始终保留
```

---

## 七、意图检测 → Agent创建

### 7.1 当前版本: 无CRSS意图系统

**重要变更**: 原CRSS意图检测系统(crss_scorer/intent_mapper/AGENT_REGISTRY)已在FC-only重构中删除。当前版本**没有意图分类**，统一由UniversalAgent处理。

```
chat_stream_v2.py → 无detect_intent调用
  ↓
run_sse_stream.py → create_agent(llm_client, task_id)
  ↓
UniversalAgent → 统一处理所有请求
  ↓
tool_search → 按需加载分类工具
```

### 7.2 tool_search 动态工具发现

```
LLM判断需要其他分类工具 → 调用 tool_search(query="xxx")
  ↓
tool_search 返回匹配结果
  ↓
Auto_inject_from_search(result)
  ├─ 解析matches → ToolCategory
  ├─ _loaded_categories.add(cat)
  ├─ tool_manager.load_category(cat)  → tool_registry动态注册
  ├─ invalidate_tool_cache()          → 清除openai_tools缓存
  └─ _patch_search_desc()             → 更新tool_search描述文本
```

### 7.3 tool_search 描述动态更新

```
_patch_search_desc()  [universal_agent.py L207-239]
  │
  ├─ 读取 tool_categories.json
  ├─ 获取未加载的分类
  ├─ 获取tool_search元数据
  ├─ 拼接未加载分类的描述:
  │     "当前未加载分类:\n- 文件操作工具(file): 文件读写... [read_text_file:...]\n- ..."
  └─ 更新 ts_meta.description (原地修改)
```

### 7.4 run_sse_stream 到前端交付

```
run_sse_stream(llm_client, task_id, last_message, ...)  [run_sse_stream.py L18-110]
  │
  ├─ L37-39: agent = create_agent(llm_client, task_id)
  │
  ├─ L45-72: async for event in agent.run_react_cycle(task=last_message):
  │  ├─ L50: event_dict = event.to_dict()
  │  ├─ L55: current_execution_steps.append(event_dict)
  │  ├─ L58-65: 更新 stream_state.current_content (final/chunk)
  │  └─ L68: sse_data = format_agent_sse(event_dict)
  │
  ├─ L74-89: CancelledError → 补发 IncidentStep(interrupted) + FinalStep
  │
  ├─ L91-97: Exception → ErrorStep
  │
  └─ L99-109: finally → save_execution_steps_to_db(session_id, execution_steps, content)
```

---

## 八、工具注册 → Schema生成 → OpenAI Tools

### 8.1 ToolRegistry

```
ToolRegistry  [registry.py]
  │
  ├─ _tools: Dict[str, ToolMetadata]         # 名称→元数据
  ├─ _implementations: Dict[str, Callable]   # 名称→实现函数
  ├─ _category_index: Dict[ToolCategory, set]  # 分类→工具名集合
  │
  ├─ register(name, description, category, implementation, input_model, ...)
  │  ├─ _generate_input_schema(input_model, input_schema)  [schema_utils.py]
  │  │  └─ _fix_schema_types()  修复Pydantic V2的type缺失
  │  └─ _register_new_tool() 或 _update_existing_tool()
  │
  ├─ to_openai_tools(categories=None) → list
  │  └─ tool_description.to_openai_tools(self, categories)
  │     └─ 遍历 _tools, 过滤 expose_to_llm + category, 生成 function定义
  │
  ├─ get_tool(name) → ToolMetadata
  ├─ get_implementation(name) → Callable
  └─ get_implementations_by_category(category) → Dict
```

### 8.2 ToolMetadata 结构

```
@dataclass
class ToolMetadata:  [tool_types.py L90-124]
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    expose_to_llm: bool = True
    next_actions: Dict[str, Any] = field(default_factory=dict)
    failure_hint_fn: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    safety_level: ToolSafetyLevel = ToolSafetyLevel SAFE
    action_safety_map: Optional[Dict[str, ToolSafetyLevel]] = None
    critical_notes: str = ""      # 关键注意事项
    usage_hint: str = ""          # 使用提示
    forbidden: str = ""           # 禁止用法
```

### 8.3 工具注册完整流程 (以文件工具为例)

```
ensure_tools_registered()  [lazy_loader.py]
  ↓ (首次调用)
CATEGORY_MODULES["file"] = ("app.services.tools.file", "_register_file_tools")
  ↓
__import__("app.services.tools.file")
  ↓
file_register._register_file_tools()  [file/file_register.py]
  ↓
@tool_registry.register(
    name="read_text_file",
    description="读取文本文件",
    category=ToolCategory.FILE,
    implementation=read_text_file,        # 实现函数
    input_model=ReadTextFileInput,         # Pydantic模型
    safety_level=ToolSafetyLevel.READ_ONLY
  )
  ↓
registry.register()
  ├─ _generate_input_schema(ReadTextFileInput, None)  → 自动从Pydantic生成JSON Schema
  ├─ _fix_schema_types(schema)  → 修复Union/Optional的type缺失
  └─ _register_new_tool()  → _tools[name] = ToolMetadata(...)
```

### 8.4 已注册工具完整清单 (50个)

| 分类 | 数量 | 工具列表 |
|------|------|---------|
| **FILE** | 10 | read_text_file, write_text_file, read_media_file, edit_text_file, list_directory, search_files, grep_file_content, archive_tool, file_operation, data_file_format |
| **FUND_RUNTIME** | 10 | execute_shell_command, find_command, shell_session, execute_code, tool_search, time_now, time_add, time_diff, query_calendar, timer |
| **NET_PROCESS** | 6 | http_request, download_file, fetch_webpage, search_web, network_diagnose, net_connections |
| **SCREEN** | 6 | window_info, window_control, mouse_control, keyboard_control, screen_capture, clipboard_control |
| **DOC_CONTENT** | 9 | read_document, write_document, convert_document, analyze_data, filter_data, generate_chart, query_sql, execute_sql, get_db_schema |
| **SYSTEM** | 9 | get_system_info, event_log, list_processes, kill_process, service_control, task_control, get_env, set_env, registry_control |

---

## 九、DB持久化 → Step存储 → 前端交付

### 9.1 Step事件类型体系

```
StepEmitter (发射器)  [step_emitter.py]
  │
  ├─ emit(StartStep) → {"type": "start", "step": 1, "display_name": "...", ...}
  ├─ emit(ChunkStep) → {"type": "chunk", "step": 1, "content": "片段", "is_reasoning": True/False}
  ├─ emit(ThoughtStep) → {"type": "thought", "step": 1, "content": "思考", "reasoning": "..."}
  ├─ emit(ActionToolStep) → {"type": "action_tool", "step": 1, "tool_name": "...", ...}
  ├─ emit(ObservationStep) → {"type": "observation", "step": 1, "observation": "...", "tool_name": "..."}
  ├─ emit(FinalStep) → {"type": "final", "step": 1, "response": "最终回答", "thought": "..."}
  ├─ emit(ErrorStep) → {"type": "error", "step": 1, "error_type": "...", "error_message": "..."}
  └─ emit(IncidentStep) → {"type": "incident", "step": 1, "incident_value": "interrupted/paused/..."}
```

### 9.2 save_execution_steps_to_db

```
save_execution_steps_to_db(session_id, execution_steps, content)  [chat_stream.py L114-143]
  │
  ├─ 检查 session_id 有效性 (非None, 不在INVALID集合中)
  ├─ _get_user_message_id(session_id)  # 从message_id_tracker获取
  │
  └─ conversation.save_execution_steps(session_id, ExecutionStepsUpdate)
     ├─ ensure_session_exists(session_id, conn)
     ├─ AssistantMessageIdAllocator.allocate(session_id, conn)  # 分配message_id
     ├─ extract_metadata_from_steps(execution_steps)  # 提取display_name等
     ├─ insert_assistant_message(...)  # 首次: 插入assistant消息
     ├─ update_message_fields(...)     # 更新execution_steps/content
     └─ update_session_message_count(...)  # 更新计数
```

### 9.3 SSE格式

```
format_agent_sse(step_dict) → str  [chat_stream.py L47-53]
  │
  ├─ event_type = step_dict.get('type', '')
  ├─ step_num = step_dict.get('step', 0)
  │
  └─ format_sse_event(event_type, step_num, step_dict) → str
     └─ f"data: {json.dumps(base, ensure_ascii=False)}\n\n"
```

---

## 十、问题分析 (按严重程度排序)

### 10.1 P0-严重

#### P0-1: tool_safety_checker 安全检查绕过风险

**文件**: `app/services/safety/tool_safety_checker.py`
**影响**: 部分危险工具未设置正确的安全级别，可能绕过安全检查

```
代码证据:
  tool_safety_checker.py:
    _check_known_risks() 只检查3类风险(路径越权/写入污染/代码注入)
    
  各分类注册文件:
    kill_process → safety_level=SAFE (默认值)  应为 DANGEROUS
    set_env → safety_level=SAFE (默认值)  应为 DESTRUCTIVE
    registry_control → safety_level=SAFE (默认值)  应为 DESTRUCTIVE
    service_control → safety_level=SAFE (默认值)  应为 DESTRUCTIVE
    task_control → safety_level=SAFE (默认值)  应为 DESTRUCTIVE
    execute_sql → safety_level=DESTRUCTIVE (已正确设置)
    execute_shell_command → safety_level=DANGEROUS (已正确设置)
    execute_code → safety_level=DANGEROUS_SANDBOX (已正确设置)
    
  → 5个系统工具使用默认SAFE级别，破坏性操作未被拦截
```

**修复建议**:
```python
# system_register.py 中显式设置安全级别
tool_registry.register(
    name="kill_process",
    ...
    safety_level=ToolSafetyLevel.DANGEROUS,  # 系统级危险
)
tool_registry.register(
    name="set_env",
    ...
    safety_level=ToolSafetyLevel.DESTRUCTIVE,  # 破坏性操作
)
# ... 对 registry_control, service_control, task_control 同样处理
```

---

#### P0-2: answer_handler 不保存assistant回复到conversation_history

**文件**: `app/services/agent/core_agent/handlers/answer_handler.py`
**影响**: 同一ReAct循环中，answer后不会有后续LLM调用，所以当前无直接问题；但如果未来需要在同一循环中支持"answer后继续"，会丢失assistant回复

```
代码证据:
  answer_handler.py L38-41:
    yield agent._step_emitter.emit(FinalStep(
        step=step, response=content, thought=thought,
    ))
    agent.status = AgentStatus.COMPLETED

  → 只emit FinalStep，没有调用任何方法保存assistant回复到conversation_history
  → message_builder.py L16 注释: "删除 add_assistant / flush_temp_to_history / add_parse_error"
  → add_assistant 被删除，没有替代方案
```

**当前影响**: 有限 — 因为answer后立即COMPLETED，不会再次调用LLM。但设计上不完整。

**修复建议**:
```python
# 在 answer_handler.py FinalStep之后添加:
# 保存assistant回复到conversation_history (为未来扩展预留)
# agent.message_builder.conversation_history.append(
#     message_to_dict(AssistantMessage(content=content))
# )
```

---

### 10.2 P1-中等

#### P1-1: StreamChunk.tool_calls 流式覆盖风险

**文件**: `app/services/agent/universal_agent.py`
**影响**: LLM返回并行tool_calls时，流式响应中tool_calls可能被多次yield，当前代码只保留最后一次

```
代码证据:
  universal_agent.py L135-136:
    if chunk.tool_calls:
        tool_calls_result = chunk.tool_calls  # 直接覆盖，不合并

  → 如果流式过程中tool_calls被分多次yield，前面的会丢失
  → 当前大多数LLM API在stream模式下tool_calls是完整返回(不分片)，风险较低
```

**修复建议**: 监控LLM API行为，如果确实出现tool_calls分片则需要合并逻辑。

---

#### P1-2: react_cycle.FAILED补发FinalStep的边界条件

**文件**: `app/services/agent/core_agent/react_cycle.py`
**影响**: 如果steps为空且状态为FAILED，不会补发FinalStep

```
代码证据:
  react_cycle.py L112:
    if agent.status == AgentStatus.FAILED and agent.steps:
    
  → 当 agent.steps 为空时跳过补发
  → 极端情况: _call_llm返回无效响应 + 无任何step发射 → FAILED但无FinalStep
  → 前端会一直等待终态事件
```

**修复建议**:
```python
# L112 改为:
if agent.status == AgentStatus.FAILED:
    # 即使steps为空，也补发FinalStep保证前端收到终态
    yield agent._step_emitter.emit(FinalStep(
        step=agent.llm_call_count,
        response="任务执行失败",
        thought="",
    ))
```

---

#### P1-3: project_context.py lru_cache对不同workdir返回错误结果

**文件**: `app/services/prompts/project_context.py`
**影响**: 如果第一次调用时workdir=None，后续workdir="xxx"会返回错误的缓存结果

```
代码证据:
  project_context.py:
    @lru_cache(maxsize=1)
    def load_project_context(workdir: str = None) -> str:
    
  → lru_cache(maxsize=1) 只缓存1个结果
  → 如果首次调用workdir=None，后续workdir="xxx"会命中缓存返回None的结果
```

**修复建议**:
```python
# 移除lru_cache，改用手动缓存
_context_cache = None
def load_project_context(workdir: str = None) -> str:
    global _context_cache
    if _context_cache is not None:
        return _context_cache
    # ... 正常逻辑
    _context_cache = result
    return result
```

---

#### P1-4: _patch_search_desc 每次调用都读文件无缓存

**文件**: `app/services/agent/universal_agent.py`
**影响**: 每次执行tool_search时都重新读取tool_categories.json，IO开销

```
代码证据:
  universal_agent.py L207-239:
    def _patch_search_desc(self):
        if not _CATEGORIES_CONFIG_PATH.exists():
            return
        with open(_CATEGORIES_CONFIG_PATH, "r", encoding="utf-8") as f:
            categories_config = json.load(f)  # 每次都读文件
```

**修复建议**: 添加文件修改时间缓存，仅在文件变化时重新读取。

---

### 10.3 P2-轻微

#### P2-1: _get_openai_tools TTL缓存300秒可能导致工具描述不更新

**文件**: `app/services/agent/universal_agent.py`
**影响**: 注册新工具后300s内LLM不会看到

```
代码证据:
  universal_agent.py L192-195:
    cache_ttl = getattr(self, '_cache_ttl', 300)
    if cached and current_time - cache_ts < cache_ttl:
        return cached

  → 有invalidate_tool_cache()机制，在工具加载变化时清除缓存
  → 实际影响较小，因为tool_search触发时会自动invalidate
```

---

#### P2-2: chunk_buffer 超时强制停止可能打断正常执行

**文件**: `app/services/agent/chunk_buffer.py` + `react_cycle.py`
**影响**: LLM正常输出也可能很长(如返回代码块)，被错误截断

```
代码证据:
  react_cycle.py L98-101:
    if chunk_buffer.should_force_stop():
        agent.status = AgentStatus.COMPLETED
        break

  → chunk_buffer.max_without_promote 默认值来自 MAX_CHUNKS_WITHOUT_PROMOTE
  → 当LLM返回大量文本(长篇解释、代码块)时，chunk累积超过阈值
```

**修复建议**: 根据实际使用情况调整阈值，或区分"正常输出"和"异常累积"。

---

#### P2-3: message_builder._cap_temp_history 50000字符限制可能过早

**文件**: `app/services/agent/message_builder.py`
**影响**: temp_history超50000字符从最旧截断，可能丢失关键上下文

```
代码证据:
  message_builder.py L134:
    while self._total_chars(self.temp_history) > TEMP_HISTORY_CHAR_LIMIT and len(self.temp_history) > 1:
        self.temp_history.pop(0)

  → TEMP_HISTORY_CHAR_LIMIT = 50000 (来自constants.py)
  → 未根据模型上下文窗口动态调整
```

---

#### P2-4: confirm_operation.py 模块级dict无上限保护

**文件**: `app/api/v1/chat/confirm_operation.py`
**影响**: 高并发下_pending_confirmations可能内存膨胀

```
代码证据:
  confirm_operation.py:
    _pending_confirmations: Dict[str, _PendingConfirmation] = {}
    
  → 虽然wait_for_confirmation_result有120秒超时，超时后Future会done
  → 但_done的_PendingConfirmation对象不会被主动清理
  → 需要确认是否有定期清理机制
```

---

#### P2-5: action_handler.build_observation 参数过多(9个)

**文件**: `app/services/agent/core_agent/handlers/action_handler.py`
**影响**: 可读性差，调用复杂

```
代码证据:
  action_handler.py L102-106:
    async def build_observation(self, agent, all_calls, results, step,
                                tool_name, tool_params, is_parallel,
                                pending_calls, action_steps,
                                fc_context=None):
```

**修复建议**: 封装为dataclass或NamedTuple，减少参数数量。

---

#### P2-6: base_agent._create_cancelled_chunk 直接访问llm_client私有方法

**文件**: `app/services/agent/core_agent/base_agent.py`
**影响**: 违反封装原则，与LLM客户端耦合

```
代码证据:
  base_agent.py L72:
    return self.llm_client._create_cancelled_chunk()
```

---

#### P2-7: react_cycle 双层getattr链式访问脆弱

**文件**: `app/services/agent/core_agent/react_cycle.py`
**影响**: 代码可读性差，访问脆弱

```
代码证据:
  react_cycle.py L58:
    if getattr(getattr(agent, 'llm_client', None), '_cancelled', False):
```

**修复建议**: 在Agent层提供 `is_cancelled` 属性。

---

### 10.4 P3-低优先级

| 编号 | 问题 | 位置 | 建议 |
|------|------|------|------|
| P3-1 | SystemPrompts只有26行，角色定义过于简单 | system_prompts.py | 建议扩展差异化Prompt |
| P3-2 | observation_formatter._get_failure_hint每次try-except导入registry | observation_formatter.py:46-54 | 改为顶部import |
| P3-3 | tool_retry_engine._find_tool找不到工具时fallback到registry但不缓存 | tool_retry_engine.py:120-122 | 可考虑缓存 |
| P3-4 | meta工具注册到FUND_RUNTIME而非独立META分类 | meta_register.py | 语义混乱 |
| P3-5 | StreamState的llm_call_count和current_content语义模糊 | chat_stream_v2.py | 建议明确文档化 |

---

## 十一、架构优点总结

| 优点 | 说明 |
|------|------|
| **SRP执行彻底** | ToolManager管加载、StepEmitter管发射、RetryEngine管重试、ChunkBuffer管缓冲、MessageBuilder管消息 |
| **FC协议一致性** | 全链路FC-only，_trim_fc_pairs确保配对完整 |
| **安全分层清晰** | Layer 2(工具级别) + Layer 3(已知风险) + HITL确认，且有安全开关 |
| **动态工具注入** | tool_search→_auto_inject_from_search→load_category，按需加载 |
| **异常闭环** | run_sse_stream.finally统一DB保存 + react_cycle.finally补发FinalStep |
| **薄调度模式** | react_cycle.py仅~120行，业务逻辑100%在handlers |
| **懒加载** | 工具注册按需触发，启动时轻量 |

---

## 十二、改进建议汇总

### 按优先级排列

| 优先级 | 改进点 | 工作量 | 影响 |
|--------|--------|--------|------|
| **P0** | 系统工具安全级别修正(kill_process/set_env/registry_control/service_control/task_control) | 10行代码 | 高 |
| **P1** | react_cycle.FAILED补发FinalStep边界条件修复 | 5行代码 | 中 |
| **P1** | project_context.py lru_cache修复 | 10行代码 | 中 |
| **P1** | _patch_search_desc文件缓存 | 15行代码 | 中 |
| **P2** | chunk_buffer阈值调整 | 1天 | 低 |
| **P2** | action_handler.build_observation参数封装 | 1天 | 低 |
| **P2** | base_agent._create_cancelled_chunk封装 | 5行 | 低 |
| **P2** | react_cycle双层getattr优化 | 5行 | 低 |
| **P3** | SystemPrompts扩展差异化Prompt | 2天 | 低 |
| **P3** | meta工具分类修正 | 半天 | 低 |

---

> 本文档基于2026-06-13实际代码架构，经5遍逐代码验证。
> 所有文件路径和行号均可在代码中验证。
> 文件路径: `G:\OmniAgentAs-desk\backend\app\`
