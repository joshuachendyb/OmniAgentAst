# OmniAgentAst Backend 核心流程深度核查报告（v2）

> 核查方式：对每个核心流程步骤进行 ≥5 次阅读/验证，覆盖正常路径、异常路径、并发路径、边界条件。
> 核查时间：2026-06-10
> 核查范围：完整主干流程 + 所有重要功能模块
> 三复核时间：2026-06-09 15:01:40 — 小沈+北京老陈
> 复核结论：5个问题中3个假问题，2个真问题已全部修复

═══════════════════════════════════════════════════════════

## 第一部分：核心关键流程梳理

### 1.1 完整主干流程（一条消息从发送到响应）

```
请求到达 → 路由 → 意图检测 → 获取LLM服务 → 注册任务 → 中断检查 → 发射start → SSE流 → Agent创建 → ReAct循环
  → LLM调用 → 解析响应 → 分派 → 安全检查 → 确认(如需) → 执行工具 → 构建observation → 追加message_builder → 输出SSE
  → (循环) → 完成 → DB保存 → 任务清理 → 返回
```

### 1.2 重要功能清单（共 17 个）

| # | 功能模块 | 文件 | 功能说明 |
|---|---------|------|---------|
| 1 | HTTP 路由层 | api/v1/chat/chat_router.py | 6个端点: /chat/stream, cancel, pause, resume, confirm, validate |
| 2 | 意图检测 CRSS | services/intents/crss_scorer.py | 双维度类型+动作评分, 5类ToolCategory |
| 3 | LLM 服务工厂 | services/factory/get_service.py | 全局缓存BaseAIService, provider/model驱动 |
| 4 | Agent 工厂 | services/agent/agent_factory.py | 配置驱动创建UniversalAgent |
| 5 | Agent 配置注册 | services/agent/agent_config.py | 5个intent_type配置: file/system/network/document/desktop |
| 6 | ReAct 循环 | services/agent/core_agent/react_cycle.py | while<max_steps: LLM→parse→dispatch→action/answer/chunk |
| 7 | LLM 响应解析 | services/agent/llm_response_parser/ | 6级handler链: dict→list→JSON-array→empty→JSON→mixed |
| 8 | 工具执行引擎 | services/agent/tool_retry_engine.py | 超时+重试(指数退避)+参数验证 |
| 9 | 工具注册表 | services/tools/registry.py | 全局单例, 装饰器注册, 按分类查询 |
| 10 | 安全检查 Checker | services/safety/tool_safety_checker.py | Layer 2: 安全级别(5级), Layer 3: 已知风险检测(路径/写入/代码注入) |
| 11 | HITL 确认机制 | api/v1/chat/confirm_operation.py | Future/Promise模式, 60s超时 |
| 12 | 任务暂停/取消 | services/task/task_registry.py | asyncio.Lock, Event驱动暂停 |
| 13 | MessageBuilder | services/agent/message_builder.py | 历史管理, 裁剪, FC配对, observation预算 |
| 14 | ChunkBuffer | services/agent/chunk_buffer.py | 连续chunk计数, 阈值promote, 强制停止 |
| 15 | Step 发射器 | services/agent/core_agent/step_emitter.py | 追加agent.steps, 返回Step对象yield给SSE |
| 16 | DB 保存 | chat_stream.py + conversation/ | 唯一保存入口, 批量保存, 异步会话ID管理 |
| 17 | 任务清理 | services/task/task_cleanup.py | registry_cleanup, 区分正常/中断 |

═══════════════════════════════════════════════════════════

## 第二部分：逐模块深度核查（≥5次/模块）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块1: 请求入口路由层 (chat_router.py + chat_stream_v2.py)

━━━ 第1次阅读: 看正常路径 ━━━
chat_router.py 接收 POST /chat/stream → 返回 StreamingResponse → 调用 chat_stream_v2(request)
chat_stream_v2:
  - 检查 messages 非空 → 取最后一条 messages[-1].content
  - detect_intent(user_input) → intent_type, confidence, candidates
  - get_service() → 全局缓存LLM实例
  - session_id = request.session_id or str(uuid4())
  - 生成器generate():
    1. task_id = uuid4()
    2. register_task(task_id, ai_service)
    3. task_interrupt_check(task_id) → 如果已取消则返回
    4. step_start(...) → yield start SSE
    5. run_sse_stream(...) → 循环 yield SSE chunks
       - 每次迭代: task_pause_check_and_yield()
       - 每次迭代: task_cancel_check_and_yield()
    6. finally: task_cleanup(task_id, llm_call_count)

━━━ 第2次阅读: 看空输入路径 ━━━
第33-37行: if not request.messages → 返回 PlainTextResponse 错误
→ 但返回的是 text/event-stream media_type。对SSE客户端来说这没问题，但严格来说应该是 text/plain。
→ 不影响功能，客户端收到错误响应后会停止解析。
→ ✅ 结论：可以接受。

━━━ 第3次阅读: 看并发路径 ━━━
get_service() 使用全局 _instance。已用 threading.Lock + double-checked locking 保护多线程安全（P1-1修复 2026-06-09）。
→ ✅ 单worker和多线程部署均安全。

━━━ 第4次阅读: 看 UUID 生成 ━━━
session_id = request.session_id or str(uuid4())
task_id = str(uuid4())
→ 如果前端传了 session_id，后端使用前端传的；否则自动生成。
→ 如果前端传了 task_id，后端**忽略**（chat_stream_v2 第47行直接用 uuid4() 覆盖了）。
   → ⚠️ 小问题：ChatRequest 模型中有 task_id 字段，但 chat_stream_v2 完全没有使用它。
   → 这是前端传 task_id 但后端不用的"静默忽略"。功能上不影响（后端自己生成），但前端若依赖此字段会困惑。
   → 🔧 已处理：删除了 models.py 中 task_id 字段。三复核确认真实问题。

━━━ 第5次阅读: 看生成器上下文 ━━━
generate() 是 async generator，StreamingResponse 消费它。
→ 如果 generate() 内部抛出未捕获异常，FastAPI 会将其包装为 500 错误。
→ 但 chat_stream_v2 的 try/except (第84-86行) 已经捕获了所有 Exception，会 yield 错误 SSE。
→ ⚠️ 问题：yield 错误 SSE 后，StreamingResponse 会继续发送这个 SSE 事件，然后生成器退出。
→ SSE 客户端会收到一个错误事件后连接关闭。这是合理的行为。
→ ✅ 异常路径处理正确。

━━━ 第6次检查: 看 step_start 和 run_sse_stream 的 yield 交织 ━━━
step_start 先 yield start SSE，然后 run_sse_stream 开始 yield chunks。
→ 顺序正确：先 start → 然后 agent 步骤 → 最后 DB 保存。
→ ✅ 流程正确。

 ━━━ 最终结论 ━━━
✅ 路由层流程正确。
⚠️ 发现1处小问题：ChatRequest.task_id 未被使用。→ ✅ 已修复：已删除models.py中task_id字段。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块2: 意图检测 (detect_intent.py + crss_scorer.py)

━━━ 第1次阅读: 看正常路径 ━━━
detect_intent(user_input) → crss_scorer.detect_intent_v2(command)
→ 计算类型分: 遍历 INTENT_MAPPING, 关键词匹配 → 得到 {ToolCategory: score}
→ 计算动作分: 遍历 ACTION_DEFINITIONS, 关键词匹配 → 得到 {action_name: score}
→ 双维度合成: 有类型分 → 动作兼容矩阵调制 → 最终分
→ 归一化: 1 - 2^(-raw) → 排序
→ 返回 (primary, candidates, confidence)
→ 如果无匹配 → 返回 (None, [], 0.0)
→ detect_intent.py 收到 None → 降级为 "system"

━━━ 第2次阅读: 看边界条件 ━━━
crss_scorer.py 第187-188行: if not command or not command.strip() → return None, [], 0.0
→ ✅ 空输入处理正确。

━━━ 第3次阅读: 看 _merge_scores ━━━
第119-137行:
  if type_scores:  # 有类型分 → 调制
  elif action_scores:  # 无类型分 → 反推
  → 只有两种分支，不会同时走两条路径。
  → ✅ 逻辑正确，没有分支泄漏。

━━━ 第4次阅读: 看 _normalize_scores ━━━
第140-146行: adjusted = 1.0 - (2.0 ** (-raw))
→ raw=0 → 1-1=0, raw=1 → 1-0.5=0.5, raw=10 → 1-很小≈1
→ 这是标准的 sigmoid-like 归一化。
→ 排序用 key=lambda x: -x[1] → 从高到低。
→ ✅ 正确。

━━━ 第5次阅读: 看 CRSS_TYPE_KEYWORDS 来源 ━━━
第35行: from app.services.tools.tool_types import INTENT_MAPPING, CRSS_TYPE_KEYWORDS
→ CRSS_TYPE_KEYWORDS 是可选的, get(type_name, {}) 安全。
→ 但 _calculate_type_scores 第86行遍历的是 INTENT_MAPPING 的 keys，不是 CRSS_TYPE_KEYWORDS 的 keys。
→ 这意味着：如果 INTENT_MAPPING 中有某个 key 在 CRSS_TYPE_KEYWORDS 中没有对应条目，kw 会是 {}，score 为 0，不会添加到 type_raw。
→ ✅ 安全。

━━━ 第6次阅读: 看 _is_negated ━──
第64-80行: 检查中文否定前缀
→ 遍历所有出现位置，只要有一个未被否定则返回 False。
→ ✅ 处理了"不要删除"→"删除"不被否定的场景。

━━━ 最终结论 ━━━
✅ 意图检测流程正确，边界处理健全。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块3: LLM 服务获取 (get_service.py + llm_core.py)

━━━ 第1次阅读: 看正常路径 ━━━
get_service():
  1. _get_resolver_and_config() → provider, model, ai_config
  2. _validate_provider_model() → 非空检查
  3. _check_cache_valid() → 命中则直接返回
  4. _cleanup_old_instance() → 关闭旧LLMClient
  5. _create_service_instance() → 创建新 BaseAIService
→ 全局变量 _instance 和 _current_provider 缓存

━━━ 第2次阅读: 看缓存失效 ━━━
如果 provider 或 model 变了：
  - _check_cache_valid: _instance is not None and _current_provider == final_provider and _instance.model == final_model
  → 任一条件不满足 → 清理旧实例 → 创建新的
  → ✅ 正确。

━━━ 第3次阅读: 看 _cleanup_old_instance ━━━
_cleanup_old_instance(new_provider):
  global _instance, _current_provider
  old_instance = _instance
  _instance = None  # ← 先设为None
  _current_provider = new_provider  # ← 再设新provider
  close_instance_sync(old_instance)  # ← 最后关闭旧实例

⚠️ 问题：在 set _instance = None 和 close_instance_sync(old_instance) 之间，如果有并发调用 get_service()，_instance is None → 检查 _current_provider 是否 == final_provider → 可能不相等 → 会创建新实例。
→ 但 get_service() 已用 threading.Lock + double-checked locking 保护（P1-1修复 2026-06-09）。
→ ✅ 多线程安全。

━━━ 第4次阅读: 看 BaseAIService._ensure_client ━━━
_llm_sdk 懒加载: 第一次调用时创建 LLMClient → httpx.AsyncClient
→ 每个 BaseAIService 实例有自己独立的 httpx 连接池。
→ ✅ 正确。

━━━ 第5次阅读: 看 BaseAIService.cancel ━━━
async def cancel(self):
  self._cancelled = True
  if self._current_response: aclose() 或 close()
→ 在 stream 中:
  if self._cancelled: yield cancelled_chunk; return
→ ✅ 取消路径正确。

━━━ 最终结论 ━━━
✅ LLM 服务获取流程正确。threading.Lock + double-checked locking 保证多线程安全。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块4: Agent 工厂与配置 (agent_factory.py + agent_config.py)

━━━ 第1次阅读: 看正常路径 ━━━
AgentFactory.create(intent_type, llm_client, task_id, ...):
  config = resolve_agent_config(intent_type)
  → normalize_intent(intent_type) → AGENT_REGISTRY[normalized_intent]
  agent_class = config.agent_class (动态import UniversalAgent)
  return agent_class(llm_client, task_id, config, ...)

━━━ 第2次阅读: 看 AGENT_REGISTRY ━━━
5个配置: file, system, network, document, desktop
→ system 有 extra_categories=[FILE] → 加载两个分类的工具
→ 其余只有单一分类
→ ✅ 正确。

━━━ 第3次阅读: 看 resolve_agent_config ━━━
def resolve_agent_config(intent_type):
  normalized = normalize_intent(intent_type)
  config = AGENT_REGISTRY.get(normalized)
  if config is None: raise ValueError(...)
→ ✅ 严格匹配，不会返回None导致后续NoneType错误。

━━━ 第4次阅读: 看 agent_class 懒加载 ━━━
@property
def agent_class(self):
  if self._agent_class is None and self.agent_module:
    import importlib → getattr(module, agent_class_name)
→ 第一次访问时动态import。如果 import 失败 → AttributeError。
→ ⚠️ 小问题：如果 agent_module 配置错误（比如模块不存在），会在 AgentFactory.create 时抛 AttributeError，不是 ValueError。
→ 但这是配置错误，运行时不会发生。
→ ✅ 可接受。

━━━ 第5次阅读: 看 candidates 传递 ━━━
AgentFactory.create(candidates=candidates) → UniversalAgent(candidates=candidates) → BaseAgent(candidates=candidates)
→ AgentInitializer._init_candidates(agent, candidates) → agent._candidates = candidates or []
→ ✅ 候选意图链正确。

━━━ 最终结论 ━━━
✅ Agent 工厂和配置流程正确。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块5: ReAct 循环 (react_cycle.py) — ★ 最核心模块

━━━ 第1次阅读: 看整体结构 ━━━
run_react_cycle(agent, task, context, max_steps, task_id):
  1. _initialize_run_state(task, task_id, context) → ChunkBuffer, 初始化历史
  2. step_counter = [0], agent.status = RUNNING
  3. while step_counter[0] < max_steps:
       async for event in _process_single_step(agent, step_counter, chunk_buffer):
           yield event
       if agent.status in (COMPLETED, FAILED): break
       if chunk_buffer.should_force_stop(): break (R10-4修复)
  4. finally: _on_after_loop(), _complete_tracked_task(success)

━━━ 第2次阅读: 看 _process_single_step ━━━
async def _process_single_step(agent, step_counter, chunk_buffer):
  step_counter[0] += 1
  llm_response = None
  async for chunk_or_response in agent._call_llm():
    if chunk_type == "chunk": yield chunk_data
    elif chunk_type == "response": llm_response = chunk_data
  
  if not llm_response: → exit_with_error(empty_response) → FAILED → return
  if agent._cancelled: → _create_cancelled_chunk → COMPLETED → return
  
  parsed = parse_llm_response(llm_response)
  parsed_type = parsed.get("type", "parse_error")
  
  handler = _TYPE_HANDLERS.get(parsed_type, _DEFAULT_HANDLER)
  async for event in handler(agent, parsed, llm_response, step_counter, chunk_buffer):
      yield event

━━━ 第3次阅读: 看 _TYPE_HANDLERS ━━━
有序字典:
  "action" → handle_action (handlers/action_handler.py)
  "answer" → handle_answer (handlers/answer_handler.py)
  "implicit" → handle_answer  (同answer)
  "chunk" → handle_chunk (handlers/chunk_handler.py)
  "parse_error" → handle_parse_error (handlers/error_handler.py)
  _DEFAULT_HANDLER = handle_unknown (handlers/error_handler.py)

⚠️ 检查: "action" 是否处理了 finish？
→ _handle_action 中没有显式处理 finish。finish 在 parse_llm_response 中被转为 "answer" 类型。
→ _build_action_from_new_format 中: is_finish = tool_name == "finish" → return type="answer"
→ ✅ 正确。finish 在解析层就转为 answer，不需要在 handler 中特殊处理。

━━━ 第4次阅读: 看 handle_action ━━━
handle_action (handlers/action_handler.py):
  1. 发射 ThoughtStep
  2. check_safety_and_confirm() → 安全检查+HITL确认(一次check_before_execute)
     → blocked → ErrorStep → return (停止)
     → requires_confirmation → create_confirmation + wait_for_confirmation_result(timeout=60)
        → not confirmed → ErrorStep → return (停止)
  3. 发射 ActionToolStep (支持并行 multiple calls)
  4. 执行工具 (asyncio.gather 并行 or 单次)
  5. 注入 _execution_result 到 action_step
  6. 构建 observation → _update_message_builder → add_observation → trim_history
  7. 发射 ObservationStep
  8. agent.message_builder.add_assistant(llm_response)

⚠️ 第2步安全检查: check_before_execute 从 tool_registry 读 safety_level
→ action_handler.py 调用 check_safety_and_confirm (合并安全检查+HITL确认)
→ 每个工具只调一次 check_before_execute，同时判断 blocked 和 requires_confirmation
→ ✅ 无重复调用。

━━━ 第5次阅读: 看 handle_answer ━━━
handle_answer:
  发射 ThoughtStep (如果有 thought)
  发射 FinalStep
  agent.status = COMPLETED
→ 外层循环检测到 COMPLETED → break
→ ✅ 正确。

━━━ 第6次阅读: 看 handle_chunk ━━━
handle_chunk:
  yield ChunkStep
  _handle_chunk_buffer_promotion: append → should_promote → flush → yield ThoughtStep + ChunkStep
→ ✅ 正确。

━━━ 第7次阅读: 看并行工具调用 ━━━
all_calls = [{tool_name, tool_params}] + pending_calls
if is_parallel (len > 1):
  results = await asyncio.gather(*tasks, return_exceptions=True)
else:
  result = await agent._execute_tool(...)

⚠️ return_exceptions=True: 如果某个工具抛异常，不会中断其他工具。结果列表中是 Exception 对象。
→ 第153-159行: if isinstance(result, Exception): 特殊处理
→ ✅ 正确处理了部分失败的场景。

━━━ 第8次阅读: 看 max_steps 保护 ━━━
while step_counter[0] < max_steps:
  → max_steps 默认 100 (agent_config.py)
  → chunk_buffer.should_force_stop() 阈值 50 chunk
→ ✅ 双重保护，不会无限循环。

 ━━━ 最终结论 ━━━
✅ ReAct 循环流程正确。handlers已拆分为handlers/目录(action/answer/chunk/error)。
⚠️ Layer 1 Hook 在 ReAct 循环中未被调用 → ✅ 三复核排除：实际架构无Hook层，tool_safety_checker.py的_check_known_risks覆盖全部场景。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块6: LLM 响应解析 (parse_llm_response.py)

━━━ 第1次阅读: 看 handler 链 ━━━
_HANDLERS = [
  _handle_dict_input,         # 1. 输入已经是 dict
  _handle_list_input,         # 2. 输入是 list
  _handle_json_array_string,  # 3. 输入是 "[{...}]" 字符串
  _handle_empty_input,        # 4. 空输入 → parse_error
  _handle_standard_json,      # 5. 输入是 {"tool_name": "..."} 字符串
  _handle_mixed_text_json,    # 6. 输入是 "Some text {"tool_name": ...}" 字符串
]

━━━ 第2次阅读: 看顺序 ━━━
如果 LLM 返回 "Here is the JSON: {"tool_name": "read"}"（带前缀文本）:
  _handle_dict_input: isinstance(str) → False → None
  _handle_list_input: isinstance(str) → False → None
  _handle_json_array_string: starts_with("[") → False → None
  _handle_empty_input: non-empty → None
  _handle_standard_json: parse_json(output) → JSONDecodeError → parse_json返回None → isinstance(dict, None) → False → None
  → ✅ 正确进入 _handle_mixed_text_json

━━━ 第3次阅读: 看 _handle_mixed_text_json ━━━
1. _extract_json_and_prefix(output) → 从尾部找 "{", 提取 JSON
2. json_data, prefix_text = result
3. if not json_data: → _build_chunk_result(output) → type="chunk"
4. tool_name = json_data.get("tool_name")
5. if tool_name == "finish": → _handle_finish_tool → type="answer"
6. if tool_name: → _build_action_result → type="action"
7. else: → _handle_implicit_content → type="implicit"

⚠️ _extract_json_with_balanced_braces 只从最后一个 "{" 开始找。
如果 LLM 返回 "Thought: {JSON1}
Action: {JSON2}"，只提取最后一个 JSON。
→ 这可能是一个问题。但通常 LLM 只有一个 JSON 块。
→ 对于并行工具调用 (pending_calls)，list handler 会处理。
→ ✅ 对单 JSON 输出正确。

━━━ 第4次阅读: 看 FC 格式处理 ━━━
_handle_standard_json: parse_json → dict → "tool_name" in data → _build_action_from_new_format
  或 "name" + "arguments" in data → _build_action_from_fc_format
→ FC格式: {"name": "read", "arguments": "{"file_path": "..."}"}
→ 解析: raw_args = parse_json(arguments_str) → dict
→ ✅ 正确。

━━━ 第5次阅读: 看 parse_error 兜底 ━━━
如果所有6个handler都返回None:
  return _build_handler_result(type_="parse_error", error="Parser chain exhausted")
→ react_cycle._process_single_step: handler = _TYPE_HANDLERS.get("parse_error", _handle_unknown)
→ _handle_parse_error → exit_with_error → FAILED
→ ✅ 不会静默失败。

━━━ 最终结论 ━━━
✅ 解析器链正确，边界处理健全。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块7: 工具执行引擎 (tool_retry_engine.py)

━━━ 第1次阅读: 看正常路径 ━━━
execute_tool_with_retry(action, action_input):
  if action == "finish": → _handle_finish → return {"data": result, "message": "Task completed"}
  tool = _find_tool(action)
    → self._tools.get(action) or tool_registry.get_implementation(action)
  params = _validate_params(action, action_input, tool)
    → _are_params_valid: schema key检查
    → _check_missing_params: inspect.signature必需参数检查
  return await _execute_with_retry(action, params, tool)

━━━ 第2次阅读: 看超时保护 ━━━
_execute_async_tool: await asyncio.wait_for(tool(**params), timeout=timeout)
_execute_sync_tool: await asyncio.wait_for(asyncio.to_thread(tool(**params)), timeout=timeout)
→ 同步工具通过 to_thread 移出事件循环 + wait_for 超时。
→ ✅ 正确。

━━━ 第3次阅读: 看重试逻辑 ━━━
_execute_with_retry:
  RetryEngine(max_retries, EXPONENTIAL, backoff_factor, _is_tool_retryable)
  while engine.attempt_count <= max_retries:
    result = await _execute_single_attempt(...)
    if result is not None: return result
    await asyncio.sleep(engine.current_delay)
→ 重试耗尽后: _build_retry_error
→ ✅ 正确。

━━━ 第4次阅读: 看 _is_async_tool ━━━
inspect.iscoroutinefunction(tool)
→ 如果工具返回 coroutine (async def)，正确识别。
→ 但如果 sync 工具内部调用了 async 操作并返回 coroutine 对象（未 await），会被误判。
→ _execute_sync_tool 第52行: if inspect.iscoroutine(result): return await wait_for(result, timeout)
→ ✅ 防御了这种情况。

━━━ 第5次阅读: 看 _handle_finish 短路 ━━━
if action == "finish": return {"data": action_input.get("result"), "message": "Task completed"}
→ 跳过所有验证和执行，直接返回成功。
→ 在 _handle_answer 中被 yield → FinalStep → COMPLETED
→ ✅ 正确。

━━━ 最终结论 ━━━
✅ 工具执行引擎流程正确，超时和重试处理健全。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块8: 安全检查 (tool_safety_checker.py)

━━━ 第1次阅读: 看 check_before_execute ━━━
check_before_execute(tool_name, params):
  tool_meta = tool_registry.get_tool(tool_name)
  → 未注册 → blocked=True, risk_score=1.0
  
  safety_level = _get_effective_safety_level(tool_meta, params)
    → action_safety_map[action] > safety_level（action级覆盖）
  policy = DEFAULT_SAFETY_POLICY[safety_level]
  
  known_risk = _check_known_risks(tool_name, params)
  → 路径越权 → blocked
  → 写入污染 → blocked
  → 代码注入 → blocked
  
  return {"is_safe", "risk_score", "safety_level", "requires_confirmation", "blocked", "message"}

━━━ 第2次阅读: 看 _check_known_risks ━━━
1. file_tools: FileTools._validate_path(path) → 路径白名单
2. _WRITE_RISK_TOOL: FileTools._check_write_safety(content, path) → 写入检查
3. code_injection_tools: DANGEROUS_PATTERNS 正则 → 代码注入检查
→ ✅ 覆盖了文件、写入、代码三大高危操作。

━━━ 第3次阅读: 看 DEFAULT_SAFETY_POLICY ━━━
5级安全级别: READ_ONLY(0.0) → SAFE(0.3) → DESTRUCTIVE(0.7) → DANGEROUS_SANDBOX(0.85) → DANGEROUS(1.0)
  DANGEROUS → needs_confirmation=True
  SAFE/READ_ONLY → needs_confirmation=False
→ ✅ 合理。

━━━ 第4次阅读: 看 react_cycle.py 中安全检查的调用位置 ━━━
action_handler.py 中: 在发射 ThoughtStep 之后、发射 ActionToolStep 之前。
check_safety_and_confirm 合并了安全检查和HITL确认，每个工具只调一次 check_before_execute。
→ ✅ 在正确的位置：先让用户看到思考过程，再通过安全拦截。

━━━ 第5次阅读: 看 HITL 确认超时 ━━━
wait_for_confirmation_result(confirm_id, timeout=60):
  await asyncio.wait_for(future, timeout=60)
  → TimeoutError → return {"confirmed": False}
  → finally: _pending_confirmations.pop(confirm_id)
→ ✅ 超时后正确清理并拒绝。

 ━━━ 最终结论 ━━━
✅ 安全检查流程正确。
架构: Layer 2 安全级别(5级) + Layer 3 已知风险检测(路径/写入/代码注入)，无Hook架构。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块9: HITL 确认机制 (confirm_operation.py)

━━━ 第1次阅读: 看流程 ━━━
_create_confirmation:
  confirm_id = f"{task_id}:{uuid4().hex[:8]}"
   future = asyncio.get_event_loop().create_future()  ← ⚠️ 应使用 get_running_loop()
   → 三复核结论：❌ 假问题。实际代码(confirm_operation.py第88行)已用 get_running_loop()，报告误报。
  _pending_confirmations[confirm_id] = _PendingConfirmation(future, time.time())
  
_wait_for_confirmation:
  entry = _pending_confirmations.get(confirm_id)
  if entry is None: → {"confirmed": False}  ← 确认请求不存在 → 直接拒绝
  await asyncio.wait_for(entry.future, timeout=60)
  → finally: pop(confirm_id)

confirm_operation(request):
  body = await request.json()
  entry = _pending_confirmations.get(confirm_id)
  if entry and not entry.future.done():
    entry.future.set_result({"confirmed": confirmed, "trust_session": trust_session})
  _cleanup_stale_confirmations()

━━━ 第2次阅读: 看清理 ━━━
_cleanup_stale_confirmations:
  if now - _last_cleanup_time < 10s: return
  stale = [k for k, v in items if future.done() or now - created_at > 60s]
  → 每10秒清理一次过期的。
  → 但 wait_for_confirmation 的 finally 也会 pop。
→ ✅ 双重清理。

━━━ 第3次阅读: 看并发安全 ━━━
_pending_confirmations 是普通 dict。在 asyncio 单线程中是安全的。
confirm_operation 和 wait_for_confirmation 可能在同一线程的不同协程中。
→ asyncio.Event/Future 是线程安全的（单线程）。
→ ✅ 正确。

━━━ 第4次阅读: 看 confirm_id 格式 ━━━
confirm_id = f"{task_id}:{uuid4().hex[:8]}"
→ task_id 是 uuid4 字符串, confirm_id 是 "uuid4:hex8"。
→ 不同 task 的 confirm_id 不会冲突 (因为 task_id 不同)。
→ ✅ 正确。

━━━ 第5次阅读: 看 confirm 调用时机 ━━━
用户在前端看到 IncidentStep (type=authorization_required) 后，在前端弹窗确认。
前端调用 POST /chat/stream/confirm → 后端 set_result。
→ 但如果用户在60s内没有确认 → wait_for 超时 → return {"confirmed": False}
→ react_cycle 中: if not auth.get("confirmed"): → ErrorStep(user_rejected) → return
→ ✅ 超时后正确中断。

 ━━━ 最终结论 ━━━
✅ HITL 确认机制流程正确。
⚠️ asyncio.get_event_loop() 应改为 get_running_loop() (P0 问题)。
→ ✅ 三复核结论：❌ 假问题。实际代码已用get_running_loop()（confirm_operation.py:88，2026-06-09已修复）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块10: 任务暂停/取消 (task_registry.py + interrupt_check.py)

━━━ 第1次阅读: 看注册 ━━━
register_task(task_id, ai_service):
  _running_tasks[task_id] = {
    "status": "running", "cancelled": False, "paused": False,
    "_pause_event": asyncio.Event()  ← 初始 set()
  }
  _pause_event.set()  ← 默认恢复状态
→ ✅ 正确。

━━━ 第2次阅读: 看暂停 ━━━
set_paused(task_id):
  _running_tasks[task_id]["paused"] = True
  _running_tasks[task_id]["status"] = "paused"
  pause_event.clear()  ← 清除事件 → 等待
→ ✅ 正确。

━━━ 第3次阅读: 看恢复 ━──
set_resumed(task_id):
  _running_tasks[task_id]["paused"] = False
  _running_tasks[task_id]["status"] = "running"
  pause_event.set()  ← 设置事件 → 唤醒
→ ✅ 正确。

━━━ 第4次阅读: 看暂停等待 ━──
task_pause_check_and_yield:
  is_paused = await check_paused()
  if is_paused:
    if not _was_paused: → emit paused event + set _was_paused = True
    await asyncio.wait_for(pause_event.wait(), timeout=300)  ← 5分钟超时
    → TimeoutError: 自动恢复
    if cancelled: return
    emit resumed event + set _was_paused = False
→ ✅ 5分钟超时防止永久挂起。

━━━ 第5次阅读: 看暂停检查的位置 ━──
chat_stream_v2 中:
  async for sse_chunk in run_sse_stream(...):
    async for pause_event in task_pause_check_and_yield(...):
      yield pause_event
    cancelled_sse = await task_cancel_check_and_yield(...)
    if cancelled_sse: break
    yield sse_chunk
  → 暂停检查在 SSE chunk 之间。
  → ⚠️ 如果在 HTTP 请求等待期间（LLM 响应慢），暂停检查不会执行。
  → 这是 P1 问题：暂停在 HTTP 等待期间不响应。
  → ✅ 三复核确认真问题。已修复：llm_core.request_stream 新增 pause_event 参数，LLM流式过程中每chunk检查暂停。

━━━ 第6次阅读: 看 cleanup ━──
cleanup_task(task_id):
  if status != "cancelled": del task  ← 正常完成 → 删除
  else: 保留  ← 中断 → 保留用于查询
→ ✅ 正确区分。

 ━━━ 最终结论 ━━━
✅ 任务管理流程正确。
⚠️ 暂停在 HTTP 等待期间不响应 (P1)。
→ ✅ 已修复：llm_core.request_stream加pause_event参数，LLM流式过程中每chunk检查暂停状态。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块11: MessageBuilder (消息管理)

━━━ 第1次阅读: 看初始化 ━──
message_builder.init_history(sys_prompt, task_prompt):
  conversation_history = [
    {"role": "system", "content": sys_prompt},
    {"role": "user", "content": task_prompt}
  ]
→ ✅ 正确。

━━━ 第2次阅读: 看 add_observation ━──
add_observation(obs_text, llm_call_count, fc_context):
  1. _prepare_observation_text: 截断到预算 + [Observation]前缀归一化
  2. _append_observation: 追加到 history
     → 有 fc_context: assistant(tool_calls) + tool(tool_call_id)
     → 无 fc_context: user role + [Tool Result]前缀
  3. trim_history()
→ ✅ 预算管理和历史裁剪正确。

━━━ 第3次阅读: 看 trim_history ━──
trim_history():
  total = _total_chars(conversation_history)
  if total < MAX * 0.8: return
  if len(history) <= 2: return
  
  system_msgs, obs_list, assistant_msgs = _classify_messages()
  budget = MAX * 0.7
  trimmed_obs = _trim_to_budget(obs_list, assistant_msgs, budget)
    → _dedup_by_fingerprint(obs_list)  ← MD5去重
    → assistant_msgs[-10:]  ← 保留最近10条assistant
    → obs_list[-30:]  ← 保留最近30条observation
    → while chars > budget: obs_list.pop(0)
  rebuilt = system_msgs + trimmed_obs + assistant_msgs
  → _trim_fc_pairs(rebuilt)  ← 确保FC配对完整
  → if len(rebuilt) >= 2: return rebuilt
  → else: return first 2 + last 8 (if total > 10)
→ ✅ 裁剪逻辑健全，FC配对保护正确。

━━━ 第4次阅读: 看 FC 配对裁剪 ━──
_trim_fc_pairs:
  assistant_ids = {tc.id for tc in assistant(tool_calls)}
  tool_ids = {tool.tool_call_id}
  paired_ids = assistant_ids & tool_ids
  → 只保留配对的
  → 没有tool_calls的assistant消息保留
  → 没有配对tool的assistant(tool_calls)消息移除
→ ✅ 正确实现了 OpenAI 的 FC 配对要求。

━━━ 第5次阅读: 看 _total_chars ━──
for msg in messages:
  content = msg.get("content")  ← 注意: 不是 msg.get("content", "")
  total += len(content) if content is not None else 0
→ ✅ 正确处理了 FC 模式下 content 为 None 的情况。

━━━ 最终结论 ━━━
✅ MessageBuilder 流程正确，边界处理完善。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块12: DB 保存 (save_execution_steps_to_db)

━━━ 第1次阅读: 看正常路径 ━──
save_execution_steps_to_db(session_id, execution_steps, content):
  if session_id is None or session_id in _INVALID_SESSION_IDS: return
  user_message_id = _get_user_message_id(session_id)
  await save_execution_steps(session_id, ExecutionStepsUpdate(...))
  → AssistantMessageIdAllocator.allocate(session_id, conn) → message_id, is_new
  → insert_assistant_message(conn, ...) if is_new
  → update_message_fields(conn, ..., execution_steps=execution_steps, content=content)
  → update_session_message_count(conn, session_id, is_new)
→ ✅ 唯一保存入口，批量保存一次。

━━━ 第2次阅读: 看异常处理 ━──
if "会话不存在" in str(e) or "404" in str(e):
  → 标记 session_id 到 _INVALID_SESSION_IDS
  → 后续请求跳过此 session
→ ✅ 正确避免了重复保存无效会话。

━━━ 第3次阅读: 看调用位置 ━──
run_sse_stream.py finally 块:
  if current_execution_steps:
    await save_execution_steps_to_db(session_id, current_execution_steps, current_content_holder[0])
→ 正常、异常、取消都走 finally → ✅ 保证保存。

━━━ 第4次阅读: 看 DB 连接 ━──
db.get_conn("chat") 作为 context manager:
  PRAGMA journal_mode=WAL  ← 并发写入优化
  PRAGMA busy_timeout=5000  ← 5秒锁等待
  → commit / rollback / close
→ ✅ 正确。

━━━ 第5次阅读: 看 save_execution_steps 内部 ━──
ensure_session_exists(session_id, conn) → 如果 session 不存在则抛出 "会话不存在"
→ save_execution_steps_to_db 捕获这个异常并标记为无效。
→ 但如果 session 存在但 messages 表为空... 不会有问题，因为 insert/update 基于 session_id 外键。
→ ✅ 正确。

 ━━━ 最终结论 ━━━
✅ DB 保存流程正确。
 ⚠️ finally 中的 save_execution_steps_to_db 如果抛异常会传播（P1 问题）。
→ 三复核：❌ 假问题。run_sse_stream.py:101-104 已用 try/except 保护 finally 中的 save 调用，异常会被记录不会传播。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### 模块13: SSE 输出流 (chat_stream.py + run_sse_stream.py)

━━━ 第1次阅读: 看 SSE 格式 ━──
format_sse_event(event_type, step, data):
  base = {'type': event_type, 'step': step, 'timestamp': ...}
  base.update(data)
  return f"data: {json.dumps(base, ensure_ascii=False)}\n\n"
→ 标准 SSE 格式: "data: {...}\n\n"
→ ✅ 正确。

━━━ 第2次阅读: 看 agent SSE 输出 ━──
format_agent_sse(step_dict, step):
  event_type = step_dict.get('type', '')
  if not event_type: return ''
  → step_dict 来自 event.to_dict() 或 dict
→ ✅ 正确。

━━━ 第3次阅读: 看 run_sse_stream ━──
agent = AgentFactory.create(...)
async for event in agent.run_react_cycle(task):
  event_dict = event if isinstance(event, dict) else event.to_dict()
  current_execution_steps.append(event_dict)
  if event_type == 'final': current_content_holder[0] = event_dict.get('response')
  elif event_type == 'chunk': current_content_holder[0] = event_dict.get('content')
  yield format_agent_sse(event_dict)
→ ✅ 累积步骤，更新内容，输出 SSE。

━━━ 第4次阅读: 看错误处理 ━──
except asyncio.CancelledError:  ← 单独捕获（不是 Exception 子类）
  agent.status = COMPLETED
except Exception as e:
  yield _yield_error_sse(...)  ← ErrorStep → SSE
finally:
  save_execution_steps_to_db(...)
→ ✅ CancelledError 单独处理正确。

━━━ 第5次阅读: 看 SSE 中断 ━──
task_cancel_check_and_yield 在循环中:
  if await check_cancelled(task_id):
    → emit incident_step(interrupted) → append to execution_steps
    → return format_agent_sse(...)
    → yield → break 循环
→ finally 中 save_execution_steps_to_db → 保存中断前的步骤
→ ✅ 正确。

━━━ 最终结论 ━━━
✅ SSE 输出流程正确。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 第三部分：核查汇总

### 核心流程完整性检查

| 步骤 | 模块 | 正确? | 备注 |
|------|------|-------|------|
| 1. 接收请求 | chat_router.py | ✅ | 空输入返回错误SSE |
| 2. 意图检测 | crss_scorer.py | ✅ | 双维度评分+兜底system |
| 3. 获取LLM服务 | get_service.py | ✅ | 全局缓存+热切换 |
| 4. 注册任务 | task_registry.py | ✅ | asyncio.Lock保护 |
| 5. 中断检查 | task_interrupt_check.py | ✅ | 前置检查 |
| 6. 发射start | step_start.py | ✅ | 含model/provider信息 |
| 7. 创建Agent | agent_factory.py | ✅ | 配置驱动+动态import |
| 8. ReAct循环 | react_cycle.py | ✅ | while<max_steps |
| 9. LLM调用 | universal_agent.py | ✅ | 流式+降级 |
| 10. 解析响应 | parse_llm_response.py | ✅ | 6级handler链 |
| 11. 安全检查 | safety/tool_safety_checker.py | ✅ | Layer 2安全级别 + Layer 3已知风险检测 |
| 12. HITL确认 | confirm_operation.py | ✅ | Future+超时 |
| 13. 执行工具 | tool_retry_engine.py | ✅ | 超时+重试 |
| 14. 构建observation | observation_formatter.py | ✅ | 成功/warning/error |
| 15. 更新历史 | message_builder.py | ✅ | 预算+裁剪+FC |
| 16. 输出SSE | chat_stream.py | ✅ | 标准格式 |
| 17. 循环检查 | interrupt_check.py | ✅ | 暂停+取消 |
| 18. DB保存 | save_execution_steps.py | ✅ | 唯一入口+finally |
| 19. 任务清理 | task_cleanup.py | ✅ | 区分正常/中断 |

**19个步骤全部核查正确。**

### 发现的问题汇总（三复核+处理状态）

| 级别 | 数量 | 问题 | 影响 | 复核定论 | 处理状态 |
|------|------|------|------|---------|---------|
| P0 | 1 | confirm_operation.py 的 asyncio.get_event_loop() | 在异步框架中可能不可靠 | ❌ 假问题 — 实际代码已用get_running_loop() | 报告误报，代码已有修复 |
| P1 | 2 | Layer 1 Hook 在 ReAct 循环未调用 | 部分安全能力未启用 | ❌ 假问题 — 实际架构无Hook层，tool_safety_checker.py的_check_known_risks覆盖路径/写入/代码注入 | 报告误判，无需处理 |
| P1 |  | 暂停在 HTTP 等待期间不响应 | 用户体验 | ✅ 真问题 — LLM流式过程中pause未检查 | ✅ **已修复** — llm_core.request_stream加pause_event参数，每chunk检查暂停 |
| P2 | 1 | ChatRequest.task_id 字段被定义但从未使用 | 前端困惑 | ✅ 真问题 — chat_stream_v2用自己的uuid4覆盖 | ✅ **已修复** — 已删除models.py中task_id字段 |
| P1 | 1 | finally中save_execution_steps_to_db抛异常传播 | 覆盖原异常，导致500 | ❌ 假问题 — run_sse_stream.py:101-104已用try/except保护finally中的save调用 | 报告误报，代码已有保护 |

### 未发现"七绕八绕"情况

主干流程是**直线型**的，没有不必要的绕路或嵌套：
- 路由 → 检测 → 创建 → 循环 → 输出 → 保存，每一步都是单向推进
- 异常路径有明确的 except/finally 处理，不会进入死胡同
- 没有多个中间层透传（已清理的纯委托函数）

---

*报告完成（v2.1修订）。每个核心流程模块核查 5-8 次，覆盖正常路径、异常路径、并发路径、边界条件。三复核后5个问题：3个假问题已排除，2个真问题已全部修复。*
