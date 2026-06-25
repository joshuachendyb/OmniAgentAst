# -*- coding: utf-8 -*-
"""
run_react_cycle — ReAct 循环核心（薄调度）

职责: 循环调度 + 类型分派，不含业务逻辑
业务逻辑在 handlers/ 目录

小健 2026-06-08
P2-5: if/elif → 注册式分派 — 小欧 2026-06-08
F4修复: _handle_action拆分SRP + _call_llm空保护 — 小欧 2026-06-08
P3-12: 删除3个纯透传函数(内联调用) — 小沈 2026-06-09
P4-01: 薄调度重构，业务逻辑移至handlers/ — 小沈 2026-06-09
FC-only重构: 删除parse_llm_response/TOOL_REMINDER/_has_tool_call, yield dict — 小沈 2026-06-11
P0-01: 删除step_counter list hack,使用agent.llm_call_count — 小沈 2026-06-13
"""

from typing import Any, Dict, Optional, AsyncGenerator

from app.utils.logger import logger
from app.services.agent.steps import ChunkStep, FinalStep, ObservationStep
from app.services.agent.types import AgentStatus
from app.services.agent.core_agent.initialize_run_state import initialize_run_state
from app.services.agent.core_agent.handlers import (
    handle_action, handle_answer,
)


def _should_retry_truncated_tool(agent, llm_response: Dict) -> bool:
    """检测LLM应答是否因输出截断导致工具调用遗漏
    
    条件:
    1. 返回类型是answer
    2. 内容很短(<500字,可能截断)
    3. 对话历史中存在带tool_calls的assistant消息(LLM之前处于工具模式)
    4. 该tool_call**未被成功执行**(无对应tool角色响应) — P0-2修复 2026-06-23 小欧
    E-3修复 2026-06-25 小欧: 阈值100→500,覆盖更多截断场景
    """
    if llm_response.get("type") != "answer":
        return False
    content = llm_response.get("content", "")
    if not content or len(content) > 500:
        return False
    history = agent.message_builder.conversation_history
    for i in range(len(history) - 1, -1, -1):
        msg = history[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            # 检查该tool_call之后是否有工具执行结果
            # 有→工具已执行,短答案是正常确认,非截断
            for j in range(i + 1, len(history)):
                next_msg = history[j]
                if next_msg.get("role") in ("tool", "observation"):
                    return False
            return True
    return False


def _dispatch_handler(agent, llm_response, chunk_buffer):
    """按type分派handler — 小健 2026-06-17 if/elif替代2-entry注册表
    E-4修复 2026-06-25 小欧: 未知类型走error而非沉默handle_answer
    """
    parsed_type = llm_response.get("type", "answer")
    if parsed_type == "action":
        return handle_action(agent, llm_response, chunk_buffer)
    if parsed_type == "answer":
        return handle_answer(agent, llm_response, chunk_buffer)
    from app.services.agent.steps import FinalStep
    from app.utils.logger import logger
    logger.warning(f"[dispatch_handler] 未知返回类型: {parsed_type}, 按answer处理")
    return handle_answer(agent, llm_response, chunk_buffer)


def _ensure_failed_final_step(agent):
    """FAILED时补发FinalStep — 小健 2026-06-17 从finally提取"""
    if agent.status != AgentStatus.FAILED:
        return
    last_err = None
    for s in reversed(agent.steps):
        err = getattr(s, '_error_message', None)
        if err:
            last_err = err
            break
    return FinalStep(
        step=agent.llm_call_count,
        response=last_err or "任务执行失败",
        thought="",
    )


def _finalize_cycle(agent):
    """循环后收尾: 状态回调+任务追踪 — 小健 2026-06-17 从finally提取"""
    agent._on_after_loop()
    agent._step_emitter.complete_task(agent.status == AgentStatus.COMPLETED)


async def _process_single_step(agent, chunk_buffer) -> AsyncGenerator:
    """处理单步循环 — FC-only: llm_response为dict,无需parse_llm_response — 小沈 2026-06-11"""

    from app.services.agent.llm_caller import call_llm
    from app.services.agent.steps import ChunkStep
    llm_response = None
    async for chunk_or_response in call_llm(agent):
        chunk_type, chunk_data = chunk_or_response

        if chunk_type == "chunk":
            # 小健 2026-06-19: StreamChunk转ChunkStep,确保emit返回Step对象
            content = chunk_data.content if hasattr(chunk_data, 'content') else str(chunk_data)
            is_reasoning = getattr(chunk_data, 'is_reasoning', False)
            chunk_step = ChunkStep(
                step=agent.llm_call_count,
                content=content,
                is_reasoning=is_reasoning,
            )
            yield agent._step_emitter.emit(chunk_step)
        elif chunk_type == "response":
            llm_response = chunk_data

    step = agent.llm_call_count

    if not llm_response or not isinstance(llm_response, dict):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        yield agent._step_emitter.exit_with_error(
            step_count=step, error_type="empty_response",
            error_message="LLM返回空响应",
        )
        agent.status = AgentStatus.FAILED
        return

    if getattr(getattr(agent, 'llm_client', None), '_cancelled', False):
        yield agent._create_cancelled_chunk()
        yield agent._step_emitter.emit(FinalStep(
            step=step,
            response="任务已被中断",
            thought="",
        ))
        agent.status = AgentStatus.COMPLETED
        return

    # BUG修复: LLM输出截断导致工具调用遗漏 — 检测preamble文本+注入重试
    if _should_retry_truncated_tool(agent, llm_response):
        content = llm_response.get("content", "")
        logger.warning(f"[run_react_cycle] 检测到LLM输出截断(step={step}, content={content[:50]}), 注入重试observation")
        obs_text = "[Observation] 工具调用输出不完整，请重新调用该工具并补充完整参数"
        agent.message_builder.add_observation(
            obs_text, {"tool_call_id": "", "tool_calls": [], "llm_content": content},
        )
        yield agent._step_emitter.emit(ObservationStep(
            step=step,
            llm_data={"summary": "LLM工具调用输出截断", "action": {}, "status": {"exec_code": "error", "message": obs_text}},
            tool_result={},
        ))
        return

    async for event in _dispatch_handler(agent, llm_response, chunk_buffer):
        yield event


async def run_react_cycle(
    agent,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
):
    """ReAct循环:调用LLM→解析→分派handler→产出Step — 小沈 2026-06-09 薄调度重构
    N-1修复 2026-06-25 小欧: 总耗时超TASK_TIMEOUT则强制结束
    """
    from app.config import get_config
    from app.constants import TASK_TIMEOUT
    import asyncio
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    chunk_buffer = initialize_run_state(agent, task, task_id, context)

    agent.status = AgentStatus.EXECUTING
    _start_time = asyncio.get_event_loop().time()

    try:
        while agent.llm_call_count < max_steps:
            if asyncio.get_event_loop().time() - _start_time > TASK_TIMEOUT.total_seconds():
                logger.warning(f"[run_react_cycle] 总耗时超TASK_TIMEOUT({TASK_TIMEOUT}), 强制结束")
                agent.status = AgentStatus.COMPLETED
                break
            async for event in _process_single_step(agent, chunk_buffer):
                yield event

            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
                break

            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({agent.llm_call_count}步),强制停止")
                agent.status = AgentStatus.COMPLETED
                break

    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        yield agent._step_emitter.exit_with_error(
            step_count=agent.llm_call_count, error_type="runtime_error", error_message=str(e),
        )
        agent.status = AgentStatus.FAILED

    finally:
        failed_step = _ensure_failed_final_step(agent)
        if failed_step:
            yield agent._step_emitter.emit(failed_step)
        _finalize_cycle(agent)
