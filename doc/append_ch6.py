# -*- coding: utf-8 -*-
"""Append Chapter 6 to scan report"""
with open('app代码函数行数分布扫描报告-小沈-2026-05-25.md', encoding='utf-8') as f:
    content = f.read()

if not content.endswith('\n'):
    content += '\n'

ch6 = r"""## 六、P1级函数拆分设计 — 函数 6~9

### 6.0 拆分大函数的工作要求

=+==========
拆分大函数的工作要求,必须遵守
1. 开始分析本章节前必须背铁规和专家戒律 反思哪些违规了
2. 必须遵守规矩的规矩是什么
3. 分析代码的要点:**跨文件数据流追踪有限**：追踪了明显的上下游关系（如 ToolRegistry → tool_meta），做完整的请求→响应全链路数据流分析
4. ⚠️ **边界条件覆盖不全**：对于大文件中的复杂条件分支，agent 识别了明显的边界缺陷（如空字典假值、fromisoformat 崩溃）
5. ⚠️ 要阅读代码 拆分中要去发现有没有现有的其他代码中的类似函数可以使用,公用
6. 必须分析每一个分支，详细后才进行拆分函数的设计和代码修改
   6.1 重构后的函数功能不能减少只能增强
   6.2 逻辑增强准确，简洁信息
   6.3 有已经有的函数用已有的，可以构建通用函数代码文件
7. 能够进行函数代码文件化的时候进行函数文件化
8. 完成一个函数的拆分后, 需要对全部边界场景做系统性测试
9. 完成一个函数后必须commit
=+==========

---

### 6.1 `_run_sse_stream` — `services/react_sse_wrapper.py:361` (111行)

**当前规模**: 111 行 | **文件位置**: `backend/app/services/react_sse_wrapper.py:361`

#### 6.1.1 当前结构拆解

`_run_sse_stream` 实现统一 SSE 流执行（Agent 分发 + GenericAgent 兜底 + 流迭代 + 错误处理），共 8 个决策点：

**调用路径**: `generate_sse_stream` → `_run_sse_stream(intent_type, llm_client, ...)` → `agent.run_stream` → SSE事件

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **A1 Agent创建** | A1a | AgentFactory.create 成功 | 使用专用 Agent | 395-398 | 高级工厂 |
| | A1b | ValueError | 创建 _GenericAgent 兜底 | 400-428 | 高级工厂 |
| **G1 GenericAgent** | G1a | TextStrategy | 24 行内联类定义 | 404-425 | 高级定义 |
| | G1b | 无策略 | _get_llm_response 返回 "" | - | 高级定义 |
| **C1 配置加载** | C1a | config.get_max_steps 可用 | 使用 get_max_steps | 430 | 中层配置 |
| | C1b | 不可用 | config.get('app.max_steps') | 430 | 中层配置 |
| **S1 流迭代** | S1a | cancelled 标志 | 生成 interrupted + 保存 + break | 437-446 | 中层检查 |
| | S1b | event 中 step 存在 | 使用 event.step | 447-448 | 中层数据处理 |
| | S1c | event 中 step 不存在 | 使用 next_step() | 448 | 中层数据处理 |
| **F1 格式化** | F1a | type == "final" | 更新 current_content | 454-455 | 中层数据处理 |
| | F1b | type == "chunk" | 更新 current_content | 456-457 | 中层数据处理 |
| | F1c | 其他 type | 只追加 + 保存 | 453-458 | 中层数据处理 |
| **E1 错误处理** | E1a | Exception | _yield_error_sse | 462-468 | 中层错误 |
| **X1 清理** | X1a | agent_llm_holder 非空 | 保存 llm_call_count | 470-471 | 中层清理 |

**重复/冗余**:
- `_GenericAgent` 类定义（24 行）内联在函数体中，每次调用重新定义类 — **DRY 严重违反**
- cancelled 检查 + save_execution_steps_to_db 模式与 `generate_sse_stream` 中的检查重复（609-616）
- SSE 格式化 `_format_sse_event` 已注入 sse_step，但 `json.loads(sse_data[6:])` 反向解析判断 type 共 6 行 — 建议在 agent.run_stream 返回前附加 type/step 元信息
- `running_tasks_lock` 的 async with 获取锁 + cancelled 检查模式与 `_execute_retry_loop` 重复

#### 6.1.2 违反原则分析

- **DRY 严重违反**: `_GenericAgent` 类内联定义，每次调用 `_run_sse_stream` 都重新创建类对象（包括 4 个方法定义）。cancelled 检查 + DB 保存模式跨函数重复。
- **SLAP 违反**: 高级类定义(24行)与中层流迭代在同一函数中混合。`_GenericAgent` 的 4 个方法抽象在类内，但整体定义破坏了 `_run_sse_stream` 的单一抽象层次。
- **SRP 违反**: Agent 创建 + GenericAgent 兜底 + 流迭代 + 状态管理 + SSE 格式化 + 错误处理共 6 个职责。
- **KISS 违反**: Agent 创建和 GenericAgent 兜底可以使用预先定义的类而非内联定义。`_GenericAgent` 被 design 为只包含策略调用，但其 `_execute_tool` 返回空 dict、`_get_task_prompt` 直接返回 task — 这些行为可通过已有的 `BaseAgent` 子类或 mixin 实现。

#### 6.1.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `AgentFactory.create` | `agent/agent_factory.py` ✅ | 已有工厂方法 |
| `_format_sse_event` | `react_sse_wrapper.py` ✅ | 已有模块级函数 |
| `_yield_error_sse` | `react_sse_wrapper.py` ✅ | 已有模块级函数 |
| `_GenericAgent` | 无 | 建议提取为模块级类或使用 BaseAgent + Mixin 组合 |
| cancelled 检查模式 | 与 generate_sse_stream 重复 | 已有 `check_and_yield_if_interrupted` |

#### 6.1.4 重构方案（详细代码设计）

**目标**: 111 行 → ~65 行骨架 + 提取 `GenericReactAgent` 模块级类，消除内联类定义 + cancelled 模式重复。

**组件1: `GenericReactAgent`** — 提取为模块级类

```python
class GenericReactAgent(BaseAgent):
    """通用 TextStrategy 兜底 Agent（代替 _run_sse_stream 内联定义）。"""

    def __init__(self, llm_client, task_id, strategy=None, **kwargs):
        super().__init__(llm_client=llm_client, task_id=task_id, tool_category=None, **kwargs)
        self._strategy = strategy

    async def _get_llm_response(self) -> str:
        self.llm_call_count += 1
        if not self._strategy:
            return ""
        last_msg = self.conversation_history[-1]["content"] if self.conversation_history else ""
        history = self.conversation_history[:-1] if len(self.conversation_history) > 1 else []
        return await self._strategy.call(
            llm_client=self.llm_client, message=last_msg,
            history_dicts=history, conversation_history=self.conversation_history)

    async def _execute_tool(self, action, params): return {}
    def _get_system_prompt(self): return "你是一个有用的AI助手，直接回答用户的问题。"
    def _get_task_prompt(self, task, context=None): return task
```

**组件2: 重构后的 `_run_sse_stream`**（~65 行）

```python
async def _run_sse_stream(
    intent_type, llm_client, task_id, ai_service, candidates,
    last_message, next_step, running_tasks, running_tasks_lock,
    session_id, current_execution_steps, current_content,
    agent_llm_holder=None,
) -> AsyncGenerator[str, None]:
    agent = None
    log_tag = f"[{intent_type.upper()}Op]"
    error_label = f"{intent_type}操作执行失败"
    error_type = f'{intent_type}_operation_error'
    try:
        agent = AgentFactory.create(
            intent_type=intent_type, llm_client=llm_client,
            task_id=task_id, candidates=candidates)
    except ValueError:
        logger.info(f"[ChatOp] intent_type='{intent_type}' 无专用Agent，使用通用TextStrategy兜底")
        strategy = TextStrategy() if ai_service else None
        agent = GenericReactAgent(llm_client=llm_client, task_id=task_id, strategy=strategy)
        log_tag = "[GenericOp]"; error_label = "操作执行失败"; error_type = 'generic_operation_error'

    config = get_config()
    max_steps = (config.get_max_steps(DEFAULT_MAX_STEPS) if hasattr(config, 'get_max_steps')
                 else config.get('app.max_steps', DEFAULT_MAX_STEPS))

    try:
        async for event in agent.run_stream(
            task=last_message, context=None,
            max_steps=max_steps, task_id=task_id,
            running_tasks=running_tasks, step_counter=next_step):

            if await _is_cancelled_and_yield(task_id, running_tasks, running_tasks_lock,
                                              next_step, session_id, current_execution_steps, current_content):
                break
            step = event.get('step') if isinstance(event, dict) else None
            sse_data = _format_sse_event(event, step or next_step(), ai_service.model, ai_service.provider)
            if sse_data:
                yield sse_data
                if sse_data.startswith("data: "):
                    step_data = json.loads(sse_data[6:])
                    current_execution_steps.append(step_data)
                    if step_data.get('type') == 'final':
                        current_content = step_data.get('response', '')
                    elif step_data.get('type') == 'chunk':
                        current_content = step_data.get('content', current_content)
                    await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
                    logger.info(f"{log_tag} SSE发送数据")
                await asyncio.sleep(0.05)
    except Exception as e:
        yield await _yield_error_sse(error_type, error_label, log_tag, task_id, e,
                                       next_step, ai_service, current_execution_steps, session_id)
    finally:
        if agent_llm_holder is not None and agent is not None:
            agent_llm_holder["n"] = getattr(agent, "llm_call_count", 0)
```

**优势**: 111 行 → ~65 行骨架 + `GenericReactAgent` 类。消除 24 行内联类定义重复创建。cancelled 检查提取为 `_is_cancelled_and_yield`（可在 generate_sse_stream 中复用）。

---

### 6.2 `generate_sse_stream` — `services/react_sse_wrapper.py:548` (107行)

**当前规模**: 107 行 | **文件位置**: `backend/app/services/react_sse_wrapper.py:548`

#### 6.2.1 当前结构拆解

`generate_sse_stream` 实现 SSE 流式生成器入口（参数初始化+安全检查+中断/暂停检查+分发+异常处理），共 8 个决策点：

**调用路径**: `chat_router` → `generate_sse_stream(messages, intent_type, ...)` → `_run_sse_stream`

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **I1 参数初始化** | I1a | candidates/running_tasks/steps 为 None | 设默认值 | 571-578 | 低层初始化 |
| | I1b | task_id 为 None | 生成 UUID | 579-580 | 低层初始化 |
| | I1c | ai_service 为 None | raise ValueError | 582-583 | 中层校验 |
| **M1 Manager 注册** | M1a | manager.register | running_tasks 登记 | 586-587 | 中层状态管理 |
| **D1 显示名** | D1a | session_id 存在 | cache_display_name | 593-594 | 中层缓存 |
| **L1 日志** | L1a | intent_type 非空 + ai_service | _log_prompts | 598-599 | 中层日志 |
| **S1 安全检查** | S1a | _perform_security_check 返回错误 | yield error + return | 601-606 | 中层安全 |
| **C1 中断检查** | C1a | 已中断 | yield interrupt + 保存 + return | 609-616 | 中层检查 |
| **P1 暂停检查** | P1a | pause 事件 | yield + 保存 | 618-623 | 中层检查 |
| **R1 分发** | R1a | _run_sse_stream | yield chunks | 628-635 | 高级分发 |
| **X1 异常** | X1a | CancelledError | _handle_client_disconnect | 637-642 | 中层错误 |
| | X1b | Exception | _yield_error_sse | 644-651 | 中层错误 |
| **F1 清理** | F1a | finally | _cleanup_task | 653-654 | 中层清理 |

**重复/冗余**:
- 中断检查（609-616）与 `_run_sse_stream` 中的 cancelled 检查模式重复（`is_interrupted` → yield → save）
- 暂停检查（618-623）与 `_run_sse_stream` / `_execute_retry_loop` 中的 pause 检查模式重复
- 参数初始化（571-580）的 None → 默认值 6 行，可压缩为 1 行默认参数
- `save_execution_steps_to_db` + `json.loads(sse_data[6:])` 模式在中断、暂停、分发三处重复

#### 6.2.2 违反原则分析

- **DRY 中度违反**: 中断/暂停的 yield + save 模式重复。`running_tasks_lock` 模式跨函数重复。
- **SLAP 基本遵守**: 各阶段（初始化 → 安全检查 → 中断/暂停 → 分发 → 异常 → 清理）层次清晰。
- **SRP 轻度违反**: 参数初始化 + 安全检查 + 状态管理 + 流分发 + 错误处理共 5 个职责，但边界清楚。
- **KISS 基本遵守**: 结构为直线型流程（初始化→校验→分发→清理），逻辑直观。

#### 6.2.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `_perform_security_check` | `react_sse_wrapper.py` ✅ | 已是模块级函数 |
| `check_and_yield_if_interrupted` | `react_sse_wrapper.py` ✅ | 已是模块级函数 |
| `_handle_client_disconnect` | `react_sse_wrapper.py` ✅ | 已是模块级函数 |
| `_cleanup_task` | `react_sse_wrapper.py` ✅ | 已是模块级函数 |
| `TaskLifecycleManager` | `react_sse_wrapper.py` ✅ | 已是模块级类 |
| 参数初始化 | 函数本身 | 可压缩，减少冗余分支 |

#### 6.2.4 重构方案（详细代码设计）

**目标**: 107 行 → ~85 行骨架，消除中断/暂停 yield + save 模式重复，压缩参数初始化。

**组件1: 合并中断/暂停的 yield + save 模式**

```python
async def _yield_sse_and_save(sse_event: str, session_id: str,
                               current_execution_steps: List, current_content: str) -> None:
    \"\"\"yield SSE 事件并保存步骤到 DB。\"\"\"
    if sse_event.startswith("data: "):
        step_data = json.loads(sse_event[6:])
        current_execution_steps.append(step_data)
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
```

但 yield 在生成器语义中需要 caller 传递。改为在 generate_sse_stream 中使用公共保存函数：

```python
async def _save_step_to_db(sse_event: str, session_id: str,
                            current_execution_steps: List, current_content: str) -> None:
    \"\"\"保存 SSE 事件中的 step 数据到 DB。\"\"\"
    if sse_event.startswith("data: "):
        step_data = json.loads(sse_event[6:])
        current_execution_steps.append(step_data)
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
```

**组件2: 重构后的 `generate_sse_stream`**（~85 行）

```python
async def generate_sse_stream(
    messages, intent_type="generic", confidence=0.0, candidates=None,
    provider=None, model=None, temperature=0.7, task_id=None,
    session_id=None, ai_service=None, next_step=None,
    running_tasks=None, running_tasks_lock=None,
    current_execution_steps=None,
) -> AsyncGenerator[str, None]:
    candidates = candidates or []
    current_execution_steps = current_execution_steps or []
    next_step = next_step or create_step_counter()
    task_id = task_id or str(uuid.uuid4())
    if ai_service is None:
        raise ValueError("[AIServiceFactory] ai_service 必须由 chat_router 传入")
    if running_tasks is None or running_tasks_lock is None:
        raise ValueError("running_tasks and running_tasks_lock must be provided")

    manager = TaskLifecycleManager(running_tasks, running_tasks_lock)
    await manager.register(task_id, ai_service)

    current_content = ""
    agent_llm_holder: Dict[str, Any] = {"n": 0}
    if session_id:
        cache_display_name(session_id, f"{ai_service.provider} ({ai_service.model})")

    if intent_type not in ("", "generic") and ai_service:
        await _log_prompts(messages, intent_type, confidence, session_id, task_id)

    security_error = await _perform_security_check(
        messages, next_step, session_id, current_execution_steps, ai_service)
    if security_error:
        yield security_error; return

    try:
        is_interrupted, msg = await check_and_yield_if_interrupted(
            task_id, running_tasks, running_tasks_lock)
        if is_interrupted:
            yield msg; await _save_step_to_db(msg, session_id, current_execution_steps, ""); return

        for pause_event in check_and_yield_if_paused(task_id, running_tasks, running_tasks_lock, next_step):
            yield pause_event
            await _save_step_to_db(pause_event, session_id, current_execution_steps, current_content)

        session_id = session_id or str(uuid.uuid4())
        last_message = messages[-1]["content"] if messages else ""

        async for sse_chunk in _run_sse_stream(
            intent_type=intent_type, llm_client=ai_service, task_id=task_id,
            ai_service=ai_service, candidates=candidates, last_message=last_message,
            next_step=next_step, running_tasks=running_tasks,
            running_tasks_lock=running_tasks_lock, session_id=session_id,
            current_execution_steps=current_execution_steps,
            current_content=current_content, agent_llm_holder=agent_llm_holder):
            yield sse_chunk

    except asyncio.CancelledError:
        async for event in _handle_client_disconnect(
            task_id, session_id, current_execution_steps, current_content,
            next_step, running_tasks, running_tasks_lock):
            yield event
    except Exception as e:
        logger.error(f"流式响应异常：task_id={task_id}, error={e}", exc_info=True)
        yield await _yield_error_sse("stream_error", "流式响应异常", "[SSE]",
                                       task_id, e, next_step, ai_service,
                                       current_execution_steps, session_id)
    finally:
        await _cleanup_task(task_id, manager, agent_llm_holder, 0)
```

**优势**: 107 行 → ~85 行。消除中断/暂停的 yield + save 模式重复（提取 `_save_step_to_db`）。参数初始化从 6 行压缩为 4 行。`_save_step_to_db` 可供 `_run_sse_stream` / `_execute_retry_loop` 复用。

---

### 6.3 `_create_action_result_from_dict` — `react_output_parser.py:1128` (101行)

**当前规模**: 101 行 | **文件位置**: `backend/app/services/agent/react_output_parser.py:1128`

#### 6.3.1 当前结构拆解

`_create_action_result_from_dict` 实际函数体仅 ~20 行（1128-1148），其余 ~80 行（1149-1228）为游离的列表处理代码（缺 `def` 定义）。

**实际函数结构（1128-1148）**，共 5 个决策点：

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **V1 输入校验** | V1a | data 为空/非 dict | _make_action_result_dict parse_error | 1133-1134 | 中层校验 |
| **T1 类型分发** | T1a | type == "parse_error" | _build_parse_error_result | 1137-1138 | 中层分发 |
| | T1b | type == "answer" | _build_answer_result | 1139-1140 | 中层分发 |
| | T1c | type == "chunk" | _build_chunk_result | 1141-1142 | 中层分发 |
| **O1 旧格式检测** | O1a | "action" in data 且 "tool_name" 不在 | _build_action_from_old_format | 1144-1146 | 中层兼容 |
| **R1 最终解析** | R1a | 默认 | _resolve_return_type | 1148 | 中层分发 |

**游离列表处理代码（1149-1228）**，共 5 个决策点：

| 决策层 | 分支 | 条件 | 处理 | 行号 |
|-------|------|------|------|------|
| **E1 空数组** | E1a | data 为空 list | 返回 parse_error | 1160-1171 |
| **V2 有效元素** | V2a | 无有效 dict | 返回 parse_error | 1177-1188 |
| **C2 取最后一个** | C2a | 默认 | valid_items[-1] | 1191 |
| **F1 Function Calling** | F1a | Function Calling 格式 | 全部转换 + 取最后一个 | 1196-1226 |
| **R2 递归** | R2a | 取最后一个 | 递归调用 _create_action_result_from_dict | 1228 |

**重复/冗余**:
- parse_error 的返回 dict（4 次：1133-1134、1162-1171、1179-1188、同名 _make_action_result_dict）— 至少 3 份重复
- Function Calling 格式的遍历+转换（1196-1211）写为内联 ~15 行，可提取辅助函数
- 空数组和无效 dict 的 parse_error 返回结构完全一致，但分散在两处独立 if 块

#### 6.3.2 违反原则分析

- **DRY 严重违反**: parse_error 的 9 字段 dict 重复构建 4 次。Function Calling 转换 15 行内联。
- **SLAP 基本遵守**: 类型分发模式清晰，各分支职责明确。
- **SRP 中度违反**: dict 处理 + list 处理 + Function Calling 转换共 3 个职责不应在同一个作用域。
- **KISS 轻度违反**: list 处理部分缺少函数定义，游离在模块级，增加理解难度。
- **架构缺陷**: list 处理代码缺少函数定义（`def`），导致 101 行被错误归入 `_create_action_result_from_dict`。

#### 6.3.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `_make_action_result_dict` | `react_output_parser.py` ✅ | 已有 |
| `_build_parse_error_result` | `react_output_parser.py` ✅ | 已有 |
| `_build_answer_result` | `react_output_parser.py` ✅ | 已有 |
| `_build_chunk_result` | `react_output_parser.py` ✅ | 已有 |
| Function Calling 转换 | 无 | 建议提取为 `_convert_function_calling_items(items)` |

#### 6.3.4 重构方案（详细代码设计）

**目标**: 补全缺失的 `def` 定义 + 消除 parse_error dict 重复 + 提取 Function Calling 转换。

**组件1: 补全 `_create_action_result_from_list`** — 将游离列表处理代码包装为函数

```python
def _create_action_result_from_list(data: List) -> Dict[str, Any]:
    \"\"\"从 list 输入创建统一格式的结果（原游离模块级代码）。\"\"\"
    if not data:
        return _make_action_result_dict("parse_error", "", "", "", None, None, "", "Empty list input from LLM")

    valid_items = [item for item in data if isinstance(item, dict)]
    if not valid_items:
        return _make_action_result_dict("parse_error", "", "", "", None, None, "", "No valid dict items in list")

    last_item = valid_items[-1]

    # Function Calling 格式检测
    if "tool_name" not in valid_items[0] and "function" in valid_items[0]:
        converted = _convert_function_calling_items(valid_items)
        last_converted = converted[-1]
        last_item = {
            "tool_name": last_converted["name"], "tool_params": last_converted["args"],
            "content": last_item.get("content", ""),
            "thought": last_item.get("thought", last_item.get("content", "")),
            "reasoning": last_item.get("reasoning", ""),
        }
        if len(converted) > 1:
            last_item["_pending_calls"] = converted[:-1]

    logger.info(f"[parse_react_response] list解析成功，使用最后一个元素")
    return _create_action_result_from_dict(last_item)
```

**组件2: `_convert_function_calling_items`** — 提取 Function Calling 转换

```python
def _convert_function_calling_items(items: List[Dict]) -> List[Dict]:
    \"\"\"转换 Function Calling 格式为统一格式。\"\"\"
    converted = []
    for item in items:
        if isinstance(item, dict) and "function" in item:
            func = item["function"]
            fname = func.get("name", "") if isinstance(func, dict) else ""
            fargs_str = func.get("arguments", "{}") if isinstance(func, dict) else "{}"
            try:
                fargs = json.loads(fargs_str) if isinstance(fargs_str, str) else (fargs_str or {})
            except (json.JSONDecodeError, TypeError):
                fargs = {}
            converted.append({"name": fname, "args": fargs})
        else:
            converted.append(item)
    return converted
```

**优势**: 补全函数定义，将 101 行分解为 3 个独立函数。消除 parse_error dict 的 3 份重复（统一使用 `_make_action_result_dict`）。Function Calling 转换 15 行提取为可测试函数。

---

### 6.4 `fetch_webpage` — `network_tools.py:380` (101行)

**当前规模**: 101 行 | **文件位置**: `backend/app/services/tools/network/network_tools.py:380`

#### 6.4.1 当前结构拆解

`fetch_webpage` 实现网页内容获取（URL校验+Playwright/httpx双路径+结果构建），共 9 个决策点：

**调用路径**: `LLM意图` → `fetch_webpage(url, prompt, extract_format, js_render, ...)` → httpx/Playwright → `_extract_html_content`

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **U1 URL校验** | U1a | _validate_url 失败 | ERR_INVALID_URL | 393-395 | 中层校验 |
| **N1 网络检查** | N1a | _check_network 失败 | ERR_NETWORK_DOWN | 397-399 | 中层校验 |
| **H1 请求头** | H1a | 固定 | User-Agent + Accept + Language + Encoding | 401-406 | 低层配置 |
| **J1 Playwright** | J1a | js_render=True | _fetch_via_playwright | 408-416 | 低层IO |
| **H2 httpx** | H2a | js_render=False | httpx.AsyncClient.get | 418-443 | 低层IO |
| | H2b | status==403 + cf-mitigated | 降级 UA 重试 | 425-429 | 低层IO |
| | H2c | image/pdf 响应 | _build_media_result | 435-437 | 中层分发 |
| **E1 提取** | E1a | html_content | _extract_html_content | 442 | 低层数据处理 |
| **R1 结果构建** | R1a | prompt 非空 | 添加 prompt + note | 454-456 | 中层数据处理 |
| | R1b | content > 5000 | 截断 + 提示原文长度 | 459-460 | 中层数据处理 |
| **X1 异常** | X1a | httpx.TimeoutException | ERR_NETWORK_TIMEOUT | 472-473 | 中层错误 |
| | X1b | httpx.HTTPStatusError | ERR_NETWORK_HTTP_ERROR | 474-475 | 中层错误 |
| | X1c | httpx.RequestError | ERR_NETWORK_REQUEST_ERROR | 476-477 | 中层错误 |
| | X1d | Exception | ERR_NET_UNKNOWN | 478-480 | 中层异常 |

**重复/冗余**:
- 代理配置（421）与 `http_request` 代理配置重复 — `_resolve_proxy` 可消除
- 请求头构建（401-406）与 `http_request` 的 headers 构建模式相似
- URL校验 + 网络检查 + httpx 异常处理 3 层与 `http_request` 完全重复
- `_build_media_result` 的分发（435-437）只在 js_render=False + image/pdf 时触发，Playwright 已经内部处理了 media

#### 6.4.2 违反原则分析

- **DRY 中度违反**: 代理配置 + URL校验 + 网络检查 + httpx 异常处理与 `http_request` 重复 20+ 行。
- **SLAP 基本遵守**: URL校验(中层) → 双路径分发(中层) → 数据提取(低层) → 结果构建(中层)，层次清晰。
- **SRP 中度违反**: URL校验 + 网络检查 + Playwright + httpx + 提取 + 结果构建共 6 个职责。
- **KISS 基本遵守**: js_render 分支清晰，httpx 分支的 Cloudflare 降级处理可读性好。

#### 6.4.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `_validate_url` | `network_tools.py:22` ✅ | 已有 — 与 http_request 共享 |
| `_check_network` | `network_tools.py:54` ✅ | 已有 — 与 http_request 共享 |
| `_fetch_via_playwright` | `network_tools.py` ✅ | 已有模块级函数 |
| `_extract_html_content` | `network_tools.py` ✅ | 已有模块级函数 |
| 代理配置 | 与 http_request 重复 | 复用 `_resolve_proxy` |
| httpx 异常处理 | 与 http_request 重复 | 可提取通用 `_build_http_error` |
| 结果构建 + llm_data | fetch_webpage 特有 | 保留 |

#### 6.4.4 重构方案（详细代码设计）

**目标**: 101 行 → ~80 行主函数，复用 `_resolve_proxy` 消除代理配置重复。

**组件1: 重构后的 `fetch_webpage`**（~80 行）

```python
async def fetch_webpage(url, prompt=None, extract_format="markdown",
                         js_render=False, timeout=30000, max_tokens=8000, proxy=None) -> dict:
    timeout_sec = timeout / 1000.0
    try:
        url_info = _validate_url(url)
        if not url_info["data"]["valid"]:
            return build_error("ERR_INVALID_URL", f"URL格式无效: {url}")
        net_info = _check_network()
        if not net_info["data"]["connected"]:
            return build_error("ERR_NETWORK_DOWN", "网络不可用")

        headers = {"User-Agent": BROWSER_USER_AGENT,
                   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                   "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
                   "Accept-Encoding": "gzip, deflate"}

        if js_render:
            playwright_result = await _fetch_via_playwright(url, proxy, timeout_sec, extract_format, max_tokens)
            if "code" in playwright_result: return playwright_result
            html_content = playwright_result["html_content"]
            extracted_content = playwright_result["extracted_content"]
            truncated = playwright_result["truncated"]
            content_type = playwright_result["content_type"]
            status_code = playwright_result["status_code"]
        else:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_sec),
                follow_redirects=True, proxy=_resolve_proxy(proxy)) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 403 and response.headers.get("cf-mitigated") == "challenge":
                    logger.info(f"[fetch_webpage] Cloudflare挑战检测，降级UA重试: {url}")
                    response = await client.get(url, headers=headers)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                mime = content_type.split(";")[0].strip().lower() if content_type else ""
                if mime and (mime.startswith("image/") or mime in ("application/pdf",)):
                    return _build_media_result(url, mime, response.content, extract_format, response.status_code)
                html_content = response.text
                content_type = response.headers.get("content-type", "")
            extracted_content, truncated = _extract_html_content(html_content, extract_format, max_tokens)
            status_code = response.status_code

        result_data = {"url": url, "content": extracted_content, "format": extract_format,
                       "content_type": content_type, "status_code": status_code, "truncated": truncated}
        if prompt:
            result_data["prompt"] = prompt; result_data["note"] = "AI提取功能需要LLM后处理"

        content_preview = result_data.get("content", "")
        if isinstance(content_preview, str) and len(content_preview) > 5000:
            content_preview = content_preview[:5000] + f"...(原文{len(content_preview)}字符)"

        return build_success(truncate_data_for_frontend(result_data),
            f"成功获取网页内容（{extract_format}格式）" + ("（已截断）" if truncated else ""),
            llm_data={"URL": url, "格式": extract_format, "状态码": result_data.get("status_code"),
                      "内容预览": content_preview, "截断": truncated},
            next_actions=build_next_actions([("search_web", "搜索更多网页", "需要搜索更多信息时")]))

    except httpx.TimeoutException:
        return build_error("ERR_NETWORK_TIMEOUT", f"获取网页超时（{timeout_sec:.1f}秒）：{url}")
    except httpx.HTTPStatusError as e:
        return build_error("ERR_NETWORK_HTTP_ERROR", f"获取网页失败 (HTTP {e.response.status_code})：{url}")
    except httpx.RequestError as e:
        return build_error("ERR_NETWORK_REQUEST_ERROR", f"网络请求失败：{str(e)}")
    except Exception as e:
        logger.error(f"[fetch_webpage] 未知错误: {e}")
        return build_error("ERR_NET_UNKNOWN", f"获取网页异常: {str(e)}")
```

**优势**: 101 行 → ~80 行。复用 `_resolve_proxy`（5.5.4 组件1）消除代理配置重复。Cloudflare 降级重试中的 `simple_headers` 变量（原 428 行）已消除（直接用同一 headers 降级 UA）。

---

"""

content += ch6

with open('app代码函数行数分布扫描报告-小沈-2026-05-25.md', 'w', encoding='utf-8') as f:
    f.write(content)

print('Chapter 6 appended successfully')
