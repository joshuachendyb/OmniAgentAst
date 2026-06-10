# -*- coding: utf-8 -*-
"""
run_react_cycle — ReAct 循环核心（薄调度）

职责: 循环调度 + 类型分派，不含业务逻辑
业务逻辑在 handlers/ 目录

小健 2026-06-08
P2-5: if/elif → 注册式分派 — 小欧 2026-06-08
F4修复: _handle_action拆分SRP + _call_llm空保护 + step_counter用int — 小欧 2026-06-08
P3-12: 删除3个纯透传函数(内联调用) — 小沈 2026-06-09
P4-01: 薄调度重构，业务逻辑移至handlers/ — 小沈 2026-06-09
"""
from typing import Any, Dict, Optional, AsyncGenerator
from collections import OrderedDict

from app.utils.logger import logger
from app.services.agent.llm_response_parser import parse_llm_response
from app.services.agent.steps import ChunkStep, FinalStep
from app.services.agent.types import AgentStatus
from app.services.agent.core_agent.handlers import (
    handle_action, handle_answer, handle_chunk,
    handle_parse_error, handle_unknown,
)
from app.services.prompts.base_prompt_template import BasePrompts


_TYPE_HANDLERS: OrderedDict[str, callable] = OrderedDict([
    ("action", handle_action),
    ("answer", handle_answer),
    ("implicit", handle_answer),
    ("chunk", handle_chunk),
    ("parse_error", handle_parse_error),
])
_DEFAULT_HANDLER = handle_unknown

_TOOL_REMINDER = BasePrompts.TOOL_REMINDER


def _has_tool_call(agent) -> bool:
    """检查当前run中是否已有工具调用 — 小沈 2026-06-10"""
    for s in getattr(agent, 'steps', []) or []:
        if hasattr(s, 'tool_name') and getattr(s, 'tool_name', None):
            return True
    return False


async def _process_single_step(agent, step_counter: list, chunk_buffer) -> AsyncGenerator:
    """处理单步循环 — async generator — 小沈 2026-06-09 支持流式chunk"""
    step_counter[0] += 1

    llm_response = None
    async for chunk_or_response in agent._call_llm():
        chunk_type, chunk_data = chunk_or_response
        
        if chunk_type == "chunk":
            yield agent._step_emitter.emit(chunk_data)
        elif chunk_type == "response":
            llm_response = chunk_data

    if not llm_response or not isinstance(llm_response, str):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        yield agent._step_emitter.exit_with_error(
            step_count=step_counter[0], error_type="empty_response",
            error_message="LLM返回空响应",
        )
        agent.status = AgentStatus.FAILED
        return

    if getattr(getattr(agent, 'llm_client', None), '_cancelled', False):
        yield agent._create_cancelled_chunk()
        yield agent._step_emitter.emit(FinalStep(
            step=step_counter[0],
            response="任务已被中断",
            thought="",
        ))
        agent.status = AgentStatus.COMPLETED
        return

    parsed = parse_llm_response(llm_response)
    parsed_type = parsed.get("type", "parse_error")

    reasoning = parsed.get("reasoning")
    if reasoning:
        yield agent._step_emitter.emit(ChunkStep(
            step=step_counter[0], content=reasoning, is_reasoning=True,
        ))

    handler = _TYPE_HANDLERS.get(parsed_type, _DEFAULT_HANDLER)
    async for event in handler(agent, parsed, llm_response, step_counter, chunk_buffer):
        yield event

    # 工具提醒: 设标志位,由_call_llm()动态注入(不永久写入conversation_history) — 小沈 2026-06-11
    if parsed_type == "chunk" and not _has_tool_call(agent):
        logger.warning(f"[react_cycle] LLM text-only response (step {step_counter[0]}), set tool_reminder flag")
        agent._tool_reminder_needed = True


async def run_react_cycle(
    agent,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
):
    """ReAct循环:调用LLM→解析→分派handler→产出Step — 小沈 2026-06-09 薄调度重构"""
    from app.config import get_config
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    chunk_buffer = agent._initialize_run_state(task, task_id, context)

    step_counter = [0]
    agent.status = AgentStatus.EXECUTING

    try:
        while step_counter[0] < max_steps:
            async for event in _process_single_step(agent, step_counter, chunk_buffer):
                yield event

            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
                break

            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({step_counter[0]}步),强制停止")
                agent.status = AgentStatus.COMPLETED
                break

    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        yield agent._step_emitter.exit_with_error(
            step_count=step_counter[0], error_type="runtime_error", error_message=str(e),
        )
        agent.status = AgentStatus.FAILED

    finally:
        # FAILED时补发FinalStep，保证前端/测试始终收到final事件 — 小沈 2026-06-10
        if agent.status == AgentStatus.FAILED and agent.steps:
            last_err = None
            for s in reversed(agent.steps):
                if hasattr(s, '_error_message') and getattr(s, '_error_message', None):
                    last_err = s._error_message
                    break
            yield agent._step_emitter.emit(FinalStep(
                step=step_counter[0],
                response=last_err or "任务执行失败",
                thought="",
            ))

        agent._on_after_loop()
        agent._complete_tracked_task(agent.status == AgentStatus.COMPLETED)
