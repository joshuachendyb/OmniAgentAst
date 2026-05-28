# -*- coding: utf-8 -*-
"""
React SSE Wrapper - SSE 流式包装层

【阶段6实现 - 2026-03-27 小沈】
从 chat2.py 复制，删除路由判断，保留通用职责。

架构：
- 第一层：chat_router.py - 路由入口（发送start步骤）
- 第二层：react_sse_wrapper.py - SSE 包装（本文件，根据intent_type分发）
- 第三层：file_react.py / network_react.py / desktop_react.py - 意图特定 Agent
- 第四层：base_react.py - 通用 ReAct 逻辑

【阶段6目标】
- 添加 intent_type 和 confidence 参数
- 根据 intent_type 分发到不同 Agent
- 使用 agent.run_stream() 返回 event dict
- 添加 SSE 格式化逻辑
- 注意：start 步骤由 chat_router 发送，本层不重复发送

【本文件说明】
- 作为服务层，不包含 FastAPI 路由
- 提供 SSE 流式生成器函数，供 chat_router.py 调用
- 保留任务管理变量和函数

Author: 小沈 - 2026-03-26
"""

import json
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, AsyncGenerator, Any, Callable
from app.services import AIServiceFactory
from app.config import get_config
from app.utils.logger import logger
from app.utils.display_name_cache import cache_display_name
from app.chat_stream.incident_handler import check_and_yield_if_interrupted, check_and_yield_if_paused, create_incident_data
from app.chat_stream.error_handler import create_error_response
from app.services.agent.reasoning_steps import StepFactory
from app.utils.time_utils import create_timestamp, create_step_counter
from app.chat_stream.chat_helpers import create_final_response
from app.chat_stream.message_saver import save_execution_steps_to_db, add_step_and_save, create_add_step_and_save, parse_and_save_sse
from app.chat_stream.sse_formatter import format_thought_sse, format_action_tool_sse, format_observation_sse, format_sse_event, format_chunk_sse
from app.services.agent.base_react import DEFAULT_MAX_STEPS
from app.services.intents.crss_scorer import CRSS_CONFIDENCE_THRESHOLD  # 【修复 2026-05-13 小沈】H2: 改为从crss_scorer导入，切断与chat_router的循环依赖
from app.services.task_lifecycle import TaskLifecycleManager  # 【重构 2026-05-25 小沈】替代直接操作running_tasks
from app.services.agent.generic_react import GenericReactAgent


async def _is_cancelled_and_yield(
    task_id: str, running_tasks: dict, running_tasks_lock: asyncio.Lock,
    next_step: Callable[[], int], session_id: str,
    current_execution_steps: list, current_content: str
) -> Optional[str]:
    """统一cancelled检查和yield逻辑 - 小沈 2026-05-25

    使用场景:
    - _run_sse_stream中cancelled检查
    - generate_sse_stream中cancelled检查

    使用示例:
        sse_data = await _is_cancelled_and_yield(...)

    返回数据说明:
        - Optional[str], 已取消则返回interrupted SSE字符串，否则None
    """
    async with running_tasks_lock:
        is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
        if is_cancelled:
            logger.info(f"[InterruptCheck] 任务 {task_id} 取消状态: {is_cancelled}")
            interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
            logger.info(f"[Step incident] 发送incident步骤(interrupted)")
            current_execution_steps.append(interrupted_data)
            await save_execution_steps_to_db(session_id, current_execution_steps, current_content or "")
            from app.chat_stream.sse_formatter import format_incident_sse
            return format_incident_sse('interrupted', '任务已被中断', step=interrupted_data.get('step'))
    return None


async def _yield_error_sse(
    error_type: str, error_label: str, log_tag: str,
    task_id: str, e: Exception, next_step, ai_service,
    current_execution_steps, session_id
) -> str:
    """统一的错误SSE响应 — 消除_run_agent_sse/_run_generic的重复错误处理"""
    logger.error(f"{log_tag} 执行出错：task_id={task_id}, error={e}", exc_info=True)
    error_step_obj = StepFactory.create_error_step(
        step=next_step(), error_type=error_type, error_message=error_label,
        recoverable=False, model=ai_service.model, provider=ai_service.provider
    )
    error_step_dict = error_step_obj.to_dict()
    error_response = format_sse_event('error', error_step_obj.step, error_step_dict)
    current_execution_steps.append(error_step_dict)
    await save_execution_steps_to_db(session_id, current_execution_steps, error_label)
    return error_response


# ============================================================
# SSE 格式化函数
# ============================================================

def dispatch_sse_event(event: Dict[str, Any], step: int, model: str, provider: str) -> str:
    """
    将 event dict 格式化为 SSE 字符串
    """
    event_type = event.get('type', '')
    
    if event_type == 'thought':
        return format_thought_sse(
            step=step,
            content=event.get('content', ''),
            thought=event.get('thought', ''),
            reasoning=event.get('reasoning', ''),
            tool_name=event.get('tool_name', event.get('action_tool', '')),
            tool_params=event.get('tool_params', event.get('params', {}))
        )
    elif event_type == 'action_tool':
        return format_action_tool_sse(
            step=step,
            tool_name=event.get('tool_name', ''),
            tool_params=event.get('tool_params', {}),
            execution_status=event.get('execution_status', 'success'),
            execution_result=event.get('execution_result'),
            execution_time_ms=event.get('execution_time_ms', 0),
            action_retry_count=event.get('action_retry_count', 0),
        )
    elif event_type == 'observation':
        return format_observation_sse(
            step=step,
            observation=event.get('observation', {}),
            code=event.get('code', ''),
            timestamp=event.get('timestamp', '')
        )
    elif event_type == 'final':
        # 【15.7修改】final字段：content→response，新增is_finished/thought/is_streaming/is_reasoning
        return create_final_response(
            content=event.get('response', ''),  # content替换为response
            step=step,
            display_name=f"{provider} ({model})",
            provider=provider,
            model=model,
            is_finished=event.get('is_finished', True),  # 【15.7新增】
            thought=event.get('thought', ''),  # 【15.7新增】
            is_streaming=event.get('is_streaming', False),  # 【15.7新增】
            is_reasoning=event.get('is_reasoning', False)  # 【15.7新增】
        )
    elif event_type == 'incident':
        # incident类型直接格式化为SSE
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    elif event_type == 'interrupted':
        # 兼容层：处理仍发送type="interrupted"的旧代码路径
        from app.chat_stream.sse_formatter import format_incident_sse
        return format_incident_sse(
            'interrupted',
            event.get('message', '用户取消了任务'),
            step=step
        )
    elif event_type == 'error':
        # 【15.7修改】error字段：删除code和message，使用新字段
        return create_error_response(
            error_type=event.get('error_type', 'agent'),
            error_message=event.get('error_message', '未知错误'),  # 改为error_message
            model=model,
            provider=provider,
            recoverable=event.get('recoverable', event.get('retryable', False)),
            step=step
        )
    elif event_type == 'chunk':
        # 【问题1修复】chunk类型：流式文本片段，支持统一ReAct流程
        return format_chunk_sse(
            event=event,
            step=step,
            model=model,
            provider=provider
        )
    else:
        # 未知类型，返回空字符串
        return ""


# ============================================================
# SSE 格式化函数 - chunk 类型处理
# ============================================================

# format_chunk_sse 已迁移到 sse_formatter.py 统一入口


# ============================================================
# 任务管理相关（服务层可被外部调用）
# ============================================================

# 任务管理字典（存储运行中的任务，用于中断）
running_tasks_lock = asyncio.Lock()
running_tasks: dict[str, dict] = {}

TASK_TIMEOUT = timedelta(hours=1)  # 1小时超时


async def cleanup_expired_tasks():
    """清理过期任务"""
    now = datetime.now()
    async with running_tasks_lock:
        expired_tasks = [
            task_id for task_id, task in running_tasks.items()
            if task.get("created_at") and now - task["created_at"] > TASK_TIMEOUT
        ]
        for task_id in expired_tasks:
            del running_tasks[task_id]
        if expired_tasks:
            logger.info(f"清理了 {len(expired_tasks)} 个过期任务")


# ============================================================
# generate_sse_stream 辅助函数 — 【重构 2026-05-25 小沈】拆分346行大函数
# ============================================================

async def _log_prompts(
    messages: List[Dict[str, str]],
    intent_type: str,
    confidence: float,
    session_id: Optional[str],
    task_id: str,
) -> None:
    """Prompt Logger记录 — 保证生命周期顺序：start_request→log_system_prompt→log_task_prompt

    使用场景:
        - generate_sse_stream中非chat意图的prompt日志记录
        - 仅记录非generic/chat意图，跳过纯聊天

    使用示例:
        await _log_prompts(messages, "file", 0.9, session_id, task_id)

    返回数据说明:
        - 无返回值，副作用为写入prompt_logger
    """
    if not messages:
        return
    user_message = ""
    for msg in messages:
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
    from app.api.v1.messages import _assistant_message_ids, _user_message_ids
    ai_message_id = _assistant_message_ids.get(session_id)
    if not ai_message_id and session_id in _user_message_ids:
        ai_message_id = _user_message_ids[session_id] + 1
    if not ai_message_id:
        return
    from app.utils.prompt_logger import get_prompt_logger
    prompt_logger = get_prompt_logger()
    prompt_logger.start_request(
        user_message=user_message,
        user_message_id=str(ai_message_id),
        session_id=session_id or task_id,
    )
    if intent_type in ("", "generic", "chat"):
        prompts_instance = None
        source_name = "通用意图：无系统Prompt"
    else:
        try:
            from app.services.agent.agent_config import resolve_agent_config
            config = resolve_agent_config(intent_type)
            prompts_instance = config.prompt_class()
            source_name = config.prompt_module.split('.')[-1] + ".py"
        except (ValueError, ImportError):
            from app.services.prompts.file import FileOperationPrompts
            prompts_instance = FileOperationPrompts()
            source_name = "file_prompts.py"
    if prompts_instance and intent_type not in ("", "generic"):
        full_prompt = prompts_instance.build_full_system_prompt()
        prompt_logger.log_system_prompt(
            step_name="系统Prompt生成",
            prompt_content=full_prompt,
            source=source_name,
            details={"intent_type": intent_type, "confidence": confidence, "note": "含OUTPUT_FORMAT(含退出规则)+TOOL_CALL_RULES+SAFETY+ROLLBACK"},
            round_number=1,
        )
    prompt_logger.log_task_prompt(
        task_content=user_message,
        context={"intent_type": intent_type, "confidence": confidence},
        round_number=1,
    )


async def _run_sse_stream(
    intent_type: str,
    llm_client,
    task_id: str,
    ai_service,
    candidates: list,
    last_message: str,
    next_step: Callable[[], int],
    running_tasks: dict,
    running_tasks_lock,
    session_id: str,
    current_execution_steps: list,
    current_content: str,
    agent_llm_holder: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """统一SSE流执行 — 合并_run_agent_sse_stream + _run_generic_sse_stream，消除~70%重复

    使用场景:
        - generate_sse_stream中分发执行SSE流
        - 先尝试AgentFactory创建专用Agent，ValueError时回退通用Agent

    使用示例:
        async for chunk in _run_sse_stream(...):
            yield chunk

    返回数据说明:
        - yield: SSE格式字符串
    """
    from app.services.agent.agent_factory import AgentFactory
    agent = None
    log_tag = f"[{intent_type.upper()}Op]"
    error_label = f"{intent_type}操作执行失败"
    error_type = f'{intent_type}_operation_error'
    try:
        agent = AgentFactory.create(
            intent_type=intent_type, llm_client=llm_client,
            task_id=task_id, candidates=candidates,
        )
    except ValueError:
        logger.info(f"[ChatOp] intent_type='{intent_type}' 无专用Agent，使用通用TextStrategy兜底")
        from app.services.agent.llm_strategies import TextStrategy
        strategy = TextStrategy() if ai_service else None
        agent = GenericReactAgent(llm_client=llm_client, task_id=task_id, strategy=strategy)
        log_tag = "[GenericOp]"
        error_label = "操作执行失败"
        error_type = 'generic_operation_error'
    config = get_config()
    max_steps = config.get_max_steps(DEFAULT_MAX_STEPS) if hasattr(config, 'get_max_steps') else config.get('app.max_steps', DEFAULT_MAX_STEPS)
    try:
        async for event in agent.run_stream(
            task=last_message, context=None,
            max_steps=max_steps, task_id=task_id,
            running_tasks=running_tasks, step_counter=next_step,
        ):
            cancelled_sse = await _is_cancelled_and_yield(
                task_id, running_tasks, running_tasks_lock, next_step,
                session_id, current_execution_steps, current_content
            )
            if cancelled_sse:
                yield cancelled_sse
                break
            event_step = event.get('step') if isinstance(event, dict) else None
            sse_step = event_step if event_step is not None else next_step()
            sse_data = dispatch_sse_event(event, sse_step, ai_service.model, ai_service.provider)
            if sse_data:
                if sse_data.startswith("data: "):
                    step_data = json.loads(sse_data[6:])
                    current_execution_steps.append(step_data)
                    if step_data.get('type') == 'final':
                        # 【P0-B3修复 小沈小健 2026-05-26】fallback到current_content，避免final.response为空时丢失chunk内容
                        current_content = step_data.get('response', current_content) or current_content
                    elif step_data.get('type') == 'chunk':
                        current_content = step_data.get('content', current_content)
                    await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
                logger.info(f"{log_tag} SSE发送数据")
                yield sse_data
                await asyncio.sleep(0.05)
    except Exception as e:
        error_response = await _yield_error_sse(
            error_type=error_type, error_label=error_label, log_tag=log_tag,
            task_id=task_id, e=e, next_step=next_step, ai_service=ai_service,
            current_execution_steps=current_execution_steps, session_id=session_id,
        )
        yield error_response
    finally:
        if agent_llm_holder is not None and agent is not None:
            agent_llm_holder["n"] = getattr(agent, "llm_call_count", 0)


async def _handle_client_disconnect(
    task_id: str,
    session_id: Optional[str],
    current_execution_steps: List[Dict],
    current_content: str,
    next_step: Callable[[], int],
    running_tasks: Dict[str, Any],
    running_tasks_lock: asyncio.Lock,
) -> AsyncGenerator[str, None]:
    """处理客户端断开连接，保存已执行步骤并yield中断SSE事件

    使用场景:
        - generate_sse_stream中CancelledError的处理
        - 需要在客户端断开后仍尝试发送interrupted事件的场景

    使用示例:
        except asyncio.CancelledError:
            async for sse_event in _handle_client_disconnect(task_id, session_id, steps, ...):
                yield sse_event

    返回数据说明:
        - yield: str类型SSE格式事件字符串
        - 如果客户端已完全断开，yield可能因GeneratorExit而跳过
    """
    async with running_tasks_lock:
        running_tasks[task_id] = {"status": "cancelled", "cancelled": True}
    interrupted_step = create_incident_data(
        incident_value='interrupted', message='客户端断开连接，任务中断', step=next_step(),
    )
    current_execution_steps.append(interrupted_step)
    try:
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
    except Exception as _save_err:
        logger.warning(f"[SSE] CancelledError后保存失败(可忽略): {_save_err}")
    try:
        interrupted_data = create_incident_data('interrupted', '客户端断开连接，任务中断')
        logger.info(f"[Step interrupted] 发送interrupted步骤(客户端断开)")
        from app.chat_stream.sse_formatter import format_incident_sse
        yield format_incident_sse('interrupted', '客户端断开连接，任务中断')
    except Exception:
        logger.info(f"[Step interrupted] 客户端已断开，跳过yield")


async def _cleanup_task(
    task_id: str,
    manager: TaskLifecycleManager,
    agent_llm_holder: Dict[str, Any],
    llm_call_count: int,
) -> None:
    """清理任务 — LLM计数日志 + TaskLifecycleManager.cleanup

    使用场景:
        - generate_sse_stream的finally块中调用

    使用示例:
        await _cleanup_task(task_id, manager, agent_llm_holder, llm_call_count)

    返回数据说明:
        - 无返回值，副作用为日志输出和running_tasks清理
    """
    reported_llm = agent_llm_holder.get("n", 0) if agent_llm_holder.get("n", 0) > 0 else llm_call_count
    logger.info(
        f"[LLM Total Counter] ====== Conversation finished, total LLM calls: {reported_llm} ======"
    )
    cleaned = await manager.cleanup(task_id)
    if cleaned:
        logger.info(f"[Cleanup] 任务 {task_id} 正常完成，已清理")
    else:
        logger.info(f"[Cleanup] 任务 {task_id} 已被中断，保留记录")


async def _save_step_to_db(
    sse_event: str, session_id: str,
    current_execution_steps: List, current_content: str
) -> None:
    """保存SSE事件中的step数据到DB - 小沈 2026-05-25

    使用场景:
    - generate_sse_stream中统一SSE保存逻辑
    - 需要保存interrupted/paused/resumed事件的场景

    使用示例:
        await _save_step_to_db(interrupt_msg, session_id, current_execution_steps, current_content)

    返回数据说明:
        - 无返回值，副作用为current_execution_steps和DB保存
    """
    if sse_event.startswith("data: "):
        step_data = json.loads(sse_event[6:])
        current_execution_steps.append(step_data)
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content)


# ============================================================
# SSE 流式生成器函数（供 chat_router.py 调用）
# ============================================================

async def generate_sse_stream(
    messages: List[Dict[str, str]],
    intent_type: str = "generic",
    confidence: float = 0.0,
    candidates: Optional[List[str]] = None,  # 【新增 2026-04-30 小沈】候选意图列表
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    ai_service: Optional[Any] = None,
    next_step: Optional[Callable[[], int]] = None,
    running_tasks: Optional[Dict[str, Any]] = None,
    running_tasks_lock: Optional[asyncio.Lock] = None,
    current_execution_steps: Optional[List[Dict]] = None
) -> AsyncGenerator[str, None]:
    """
    SSE 流式生成器 - 实时展示ReAct执行步骤（骨架 ≤80行）
    
    供 chat_router.py 调用，返回 AsyncGenerator 用于 SSE 流式输出。
    【重构 2026-05-25 小沈】拆分为5个辅助函数 + TaskLifecycleManager。
    注意：start 步骤由 chat_router 发送，本层只处理分发后的逻辑。
    """
    if candidates is None:
        candidates = []
    if running_tasks is None or running_tasks_lock is None:
        raise ValueError("running_tasks and running_tasks_lock must be provided")
    if current_execution_steps is None:
        current_execution_steps = []
    if next_step is None:
        next_step = create_step_counter()
    if not task_id:
        task_id = str(uuid.uuid4())

    if ai_service is None:
        raise ValueError("[AIServiceFactory] react_sse_wrapper 禁止创建 ai_service，必须由 chat_router 传入")
    logger.info(f"[AIServiceFactory] 使用 router 传入的 ai_service（复用）")

    manager = TaskLifecycleManager(running_tasks, running_tasks_lock)
    await manager.register(task_id, ai_service)

    llm_call_count = 0
    agent_llm_holder: Dict[str, Any] = {"n": 0}
    current_content: str = ""
    display_name = f"{ai_service.provider} ({ai_service.model})"
    if session_id:
        cache_display_name(session_id, display_name)

    logger.info(f"[LLM Total Counter] ====== New conversation started, counter reset to 0 ======")

    if intent_type not in ("", "generic") and ai_service:
        await _log_prompts(messages, intent_type, confidence, session_id, task_id)

    try:
        is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(task_id, running_tasks, running_tasks_lock)
        if is_interrupted:
            yield interrupt_msg
            await _save_step_to_db(interrupt_msg, session_id, current_execution_steps, current_content or "")
            return

        async for pause_event in check_and_yield_if_paused(task_id, running_tasks, running_tasks_lock):
            yield pause_event
            await _save_step_to_db(pause_event, session_id, current_execution_steps, current_content or "")

        session_id = session_id or str(uuid.uuid4())
        last_message = messages[-1]["content"] if messages else ""

        async for sse_chunk in _run_sse_stream(
            intent_type=intent_type, llm_client=ai_service, task_id=task_id,
            ai_service=ai_service, candidates=candidates, last_message=last_message,
            next_step=next_step, running_tasks=running_tasks, running_tasks_lock=running_tasks_lock,
            session_id=session_id, current_execution_steps=current_execution_steps,
            current_content=current_content, agent_llm_holder=agent_llm_holder,
        ):
            yield sse_chunk

    except asyncio.CancelledError:
        async for sse_event in _handle_client_disconnect(
            task_id, session_id, current_execution_steps, current_content,
            next_step, running_tasks, running_tasks_lock,
        ):
            yield sse_event

    except Exception as e:
        logger.error(f"流式响应异常：task_id={task_id}, error={e}", exc_info=True)
        error_response = await _yield_error_sse(
            error_type="stream_error", error_label="流式响应异常", log_tag="[SSE]",
            task_id=task_id, e=e, next_step=next_step, ai_service=ai_service,
            current_execution_steps=current_execution_steps, session_id=session_id,
        )
        yield error_response

    finally:
        await _cleanup_task(task_id, manager, agent_llm_holder, llm_call_count)


# ============================================================
# 任务控制函数（供外部调用）
# ============================================================

async def cancel_task(task_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    中断指定的流式任务
    
    【方案4改进】增强中断响应机制：
    1. 立即设置cancelled状态
    2. 强制关闭LLM HTTP连接
    3. 返回详细的状态信息
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选，用于阻止重连）
    
    Returns:
        {"success": bool, "message": str, "task_status": str}
    """
    # 记录中断时间戳
    interrupt_time = datetime.now()
    
    async with running_tasks_lock:
        logger.info(f"[TaskControl] 当前running_tasks数量: {len(running_tasks)}, keys: {list(running_tasks.keys())}")
        
        if task_id in running_tasks:
            task_info = running_tasks[task_id]
            task_info["cancelled"] = True
            task_info["status"] = "cancelled"
            task_info["interrupt_time"] = interrupt_time.isoformat()  # 【方案4】记录中断时间
            task_info["cancel_request_time"] = interrupt_time.timestamp()  # 【时间测量】记录取消请求时间
            
            # 【日志增强】记录任务详细信息和时间差
            now_ts = interrupt_time.timestamp()
            logger.info(f"[TaskControl] 中断任务 {task_id}，时间戳: {now_ts}")
            logger.info(f"[TaskControl] ai_service存在: {'ai_service' in task_info}")
            logger.info(f"[TaskControl] 任务步骤: {task_info.get('current_step', 'unknown')}")
            
            # 【2026-05-13 小沈】优先用asyncio.Task.cancel()真正中断运行中的生成器
            running_task = task_info.pop("_task", None)
            if running_task is not None and not running_task.done():
                running_task.cancel()
                logger.info(f"[Task Cancelled] 任务 {task_id} asyncio.Task.cancel() 已调用")
            
            # 【方案4】强制关闭HTTP连接（兜底）
            if "ai_service" in task_info and task_info["ai_service"]:
                ai_service = task_info["ai_service"]
                try:
                    ai_service.cancel()
                    logger.info(f"[Task Cancelled] 任务 {task_id} HTTP连接已强制关闭")
                except Exception as e:
                    logger.error(f"[Task Cancelled] 关闭HTTP连接失败: {e}")
            
            # 从 running_tasks 中移除任务（避免内存泄漏）
            # 修改：不立即删除，设置为cancelled状态保留记录
            # del running_tasks[task_id]  # 不要立即删除
            # 改为设置状态为已取消，但保留记录
            task_info["status"] = "cancelled"
            task_info["cancelled"] = True
            task_info["interrupt_time"] = interrupt_time.isoformat()
            logger.info(f"[Task Cancelled] 任务 {task_id} 已标记为cancelled，保留记录")
            
            # 返回更详细的状态信息
            return {
                "success": True, 
                "message": f"任务 {task_id} 已中断",
                "task_status": "cancelled",
                "interrupt_time": interrupt_time.isoformat()
            }
        else:
            logger.warning(f"[TaskControl] 任务 {task_id} 不在running_tasks中，可能已结束")
            return {"success": False, "message": f"任务 {task_id} 不存在", "task_status": "not_found"}


async def pause_task(task_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    暂停指定的流式任务
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选）
    
    Returns:
        {"success": bool, "message": str}
    """
    if session_id:
        logger.info(f"[Pause] 会话 {session_id} 暂停任务 {task_id}")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            # 如果任务已被中断，不能暂停
            if running_tasks[task_id].get("cancelled", False):
                return {"success": False, "message": f"任务 {task_id} 已被中断，无法暂停"}
            running_tasks[task_id]["paused"] = True
            running_tasks[task_id]["status"] = "paused"
            logger.info(f"[Pause] 任务 {task_id} 已暂停")
            return {"success": True, "message": f"任务 {task_id} 已暂停"}
        return {"success": False, "message": f"任务 {task_id} 不存在"}


async def resume_task(task_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    继续指定的流式任务
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选）
    
    Returns:
        {"success": bool, "message": str}
    """
    if session_id:
        logger.info(f"[Resume] 会话 {session_id} 恢复任务 {task_id}")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            # 如果任务已被中断，不能恢复
            if running_tasks[task_id].get("cancelled", False):
                return {"success": False, "message": f"任务 {task_id} 已被中断，无法恢复"}
            # 如果任务没有暂停，不能恢复
            if not running_tasks[task_id].get("paused", False):
                return {"success": False, "message": f"任务 {task_id} 未暂停，无法恢复"}
            running_tasks[task_id]["paused"] = False
            running_tasks[task_id]["status"] = "running"
            logger.info(f"[Resume] 任务 {task_id} 已继续")
            return {"success": True, "message": f"任务 {task_id} 已继续"}
        return {"success": False, "message": f"任务 {task_id} 不存在"}
