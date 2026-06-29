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

import asyncio
from typing import Any, Dict, Optional, AsyncGenerator

from app.utils.logger import logger
from app.config import get_config
from app.constants import TASK_TIMEOUT
from app.services.agent.steps import ChunkStep, FinalStep, ObservationStep, ErrorStep
from app.services.agent.types import AgentStatus
from app.services.agent.core_agent.initialize_run_state import initialize_run_state
from app.services.agent.core_agent.handlers import (
    handle_action, handle_answer,
)
from app.services.agent.core_agent.error_handler import handle_react_error

_MAX_CONSECUTIVE_TRUNCATIONS = 3


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


async def _dispatch_handler(agent, llm_response, chunk_buffer):
    """按type分派handler — 小健 2026-06-17 if/elif替代2-entry注册表
    北京老陈 2026-06-25: 未知类型走FAILED而非handle_answer
    """
    parsed_type = llm_response.get("type", "answer")
    if parsed_type == "action":
        async for event in handle_action(agent, llm_response, chunk_buffer):
            yield event
    elif parsed_type == "answer":
        async for event in handle_answer(agent, llm_response, chunk_buffer):
            yield event
    elif parsed_type == "error":
        # 【E-4修复】error类型—建ErrorStep+set_failed — 小欧 2026-06-28
        content = llm_response.get("content", "")
        agent.message_builder.add_assistant_message(content or "")
        agent.set_failed(content or "LLM流式错误")
        yield agent._step_emitter.emit(ErrorStep(
            step=agent.llm_call_count,
            error_type="llm_error",
            error_message=content or "LLM流式错误",
        ))
    else:
        logger.warning(f"[dispatch_handler] 未知返回类型: {parsed_type}, 设置为FAILED")
        # 【#35修复】未知类型响应加入对话历史，防止LLM重复产生相同无效响应 — chendyg 2026-06-26
        content = llm_response.get("content", "") or llm_response.get("thought", "")
        if content:
            agent.message_builder.add_assistant_message(f"[无效响应:{parsed_type}] {content}")
        agent.set_failed(f"LLM返回未知响应类型: {parsed_type}")
        yield agent._step_emitter.emit(FinalStep(
            step=agent.llm_call_count,
            response=f"LLM返回未知响应类型: {parsed_type}",
            thought="",
        ))


def _ensure_failed_final_step(agent):
    """FAILED时补发FinalStep — 小健 2026-06-17 从finally提取
    小健 2026-06-26: 修复P0-5 RETRYABLE_ERROR不应补发FinalStep，由循环继续处理"""
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
    """处理单步循环 — call_llm内联, 直接调用call_llm_stream — 小欧 2026-06-25"""

    from app.services.agent.llm_stream import call_llm_with_fallback
    from app.services.agent.tool_cache_manager import get_openai_tools
    from app.services.agent.steps import ChunkStep
    from app.utils.prompt_logger import get_prompt_logger

    agent.llm_call_count += 1
    agent.message_builder.trim_history()
    messages = agent.message_builder.prepare_messages_for_llm()
    openai_tools = get_openai_tools(agent)

    logger.info(f"[FC] LLM调用#{agent.llm_call_count}, messages={len(messages)}, tools={len(openai_tools)}, model={getattr(agent.llm_client, 'model', '?')}")

    prompt_logger = get_prompt_logger()
    prompt_logger.log_llm_call(
        round_number=agent.llm_call_count,
        messages=messages,
        model=getattr(agent.llm_client, 'model', 'unknown'),
        provider=getattr(agent.llm_client, 'provider', 'unknown'),
        call_type="tools",
        tools=openai_tools,
    )

    if not openai_tools:
        logger.error("[_process_single_step] 无可用工具")

    llm_response = None
    async for chunk_or_response in call_llm_with_fallback(agent, messages, openai_tools):
        chunk_type, chunk_data = chunk_or_response

        if chunk_type == "chunk":
            content = chunk_data.content if hasattr(chunk_data, 'content') else str(chunk_data)
            is_reasoning = getattr(chunk_data, 'is_reasoning', False)
            # 【P1-13修复】chunk_buffer.append使should_force_stop生效 — chendyg 2026-06-26
            chunk_buffer.append(content)
            chunk_step = ChunkStep(
                step=agent.llm_call_count,
                content=content,
                is_reasoning=is_reasoning,
            )
            yield agent._step_emitter.emit(chunk_step)
        elif chunk_type == "response":
            llm_response = chunk_data
            # 【P1-13修复】收到完整响应时重置chunk计数器 — chendyg 2026-06-26
            chunk_buffer.clear()

    step = agent.llm_call_count

    if not llm_response or not isinstance(llm_response, dict):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        yield agent._step_emitter.exit_with_error(
            step_count=step, error_type="empty_response",
            error_message="LLM返回空响应",
        )
        return

    if getattr(getattr(agent, 'llm_client', None), '_cancelled', False):
        yield agent._create_cancelled_chunk()
        yield agent._step_emitter.emit(FinalStep(
            step=step,
            response="任务已被中断",
            thought="",
        ))
        # 【Bug17修复】取消应设CANCELLED而非COMPLETED — chendyg 2026-06-26
        agent.set_cancelled()
        return

    # B3修复: LLM未调用任何工具直接回答 → 注入警告并重试 — 小欧 2026-06-26
    if (llm_response.get("type") == "answer"
            and llm_response.get("content")
            and not getattr(agent, '_notool_retried', False)):
        has_tool_results = any(
            msg.get("role") == "tool"
            for msg in agent.message_builder.conversation_history
        )
        if not has_tool_results:
            content = llm_response.get("content", "")
            agent._notool_retried = True
            logger.warning(f"[B3] LLM返回answer但未调用任何工具(step={step}), 注入警告并重试")
            obs_text = "[Observation] 警告: 你未调用任何工具获取实时数据。必须复核3遍用户的任务,是否需要工具调用,尤其是对于需要系统状态、文件内容、时间信息等数据的任务，你必须使用相关工具获取准确数据，不能凭记忆编造。请重新使用工具获取数据后回答。"
            agent.message_builder.add_observation(
                obs_text, {"tool_call_id": "", "tool_calls": [], "llm_content": content},
            )
            yield agent._step_emitter.emit(ObservationStep(
                step=step,
                llm_data={"summary": "LLM未调用工具直接回答", "action": {}, "status": {"exec_code": "error", "message": obs_text}},
                tool_result={},
            ))
            return

    # BUG修复: LLM输出截断导致工具调用遗漏 — 检测preamble文本+注入重试
    if _should_retry_truncated_tool(agent, llm_response):
        content = llm_response.get("content", "")
        agent._consecutive_truncations = getattr(agent, '_consecutive_truncations', 0) + 1
        logger.warning(f"[run_react_cycle] 检测到LLM输出截断(step={step}, 连续第{agent._consecutive_truncations}次, content={content[:50]})")

        if agent._consecutive_truncations >= _MAX_CONSECUTIVE_TRUNCATIONS:
            logger.error(f"[run_react_cycle] LLM连续截断{_MAX_CONSECUTIVE_TRUNCATIONS}次, 停止重试, 设为FAILED")
            agent.set_failed(f"LLM连续{_MAX_CONSECUTIVE_TRUNCATIONS}次输出截断")
            yield agent._step_emitter.emit(FinalStep(
                step=step,
                response=f"LLM连续{_MAX_CONSECUTIVE_TRUNCATIONS}次输出截断",
                thought="",
            ))
            return

        obs_text = "[Observation] 工具调用输出不完整，请重新调用该工具并补充完整参数"
        # 【P1-8修复】截断重试需从历史中找到未完成的tool_call_id，不能传空 — chendyg 2026-06-26
        _retry_tc_id = ""
        history = agent.message_builder.conversation_history
        for i in range(len(history) - 1, -1, -1):
            msg = history[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                _retry_tc_id = msg["tool_calls"][-1].get("id", "")
                break
        agent.message_builder.add_observation(
            obs_text, {"tool_call_id": _retry_tc_id, "tool_calls": [], "llm_content": content},
        )
        yield agent._step_emitter.emit(ObservationStep(
            step=step,
            llm_data={"summary": "LLM工具调用输出截断", "action": {}, "status": {"exec_code": "error", "message": obs_text}},
            tool_result={},
        ))
        return

    # 正常响应, 重置截断计数器
    agent._consecutive_truncations = 0
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
    Batch2c: 导入移文件顶部 — 小欧 2026-06-25
    """
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    chunk_buffer = initialize_run_state(agent, task, task_id, context)

    # 【P1-12修复】max_steps<=0时直接FAILED，避免无终态 — chendyg 2026-06-26
    if max_steps <= 0:
        logger.warning(f"[run_react_cycle] max_steps={max_steps}, 直接设为FAILED")
        agent.set_failed(f"max_steps={max_steps}, 无可用步骤")
        yield agent._step_emitter.emit(FinalStep(
            step=0, response=f"max_steps={max_steps}, 无可用步骤", thought="",
        ))
        _finalize_cycle(agent)
        return

    agent.status = AgentStatus.EXECUTING
    _start_time = asyncio.get_event_loop().time()

    try:
        while agent.llm_call_count < max_steps:
            if asyncio.get_event_loop().time() - _start_time > TASK_TIMEOUT.total_seconds():
                logger.warning(f"[run_react_cycle] 总耗时超TASK_TIMEOUT({TASK_TIMEOUT}), 强制结束")
                agent.set_failed(f"总耗时超TASK_TIMEOUT({TASK_TIMEOUT})")
                yield agent._step_emitter.emit(ErrorStep(step=agent.llm_call_count, error_type="timeout", error_message=f"ReAct循环执行超时，耗时{asyncio.get_event_loop().time() - _start_time:.1f}秒"))
                break
            async for event in _process_single_step(agent, chunk_buffer):
                yield event


            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED):
                break

            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({agent.llm_call_count}步),强制停止")
                agent.set_failed(f"chunk累积超时({agent.llm_call_count}步)")
                yield agent._step_emitter.emit(ErrorStep(step=agent.llm_call_count, error_type="chunk_buffer_timeout", error_message="chunk buffer累积超时，强制停止"))
                break

        # 【修复】循环自然结束（max_steps耗尽）但无终态→强制FAILED — 小欧 2026-06-28
        if agent.status not in (
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,

        ):
            logger.warning(f"[run_react_cycle] 循环结束无终态(status={agent.status}), 设为FAILED")
            agent.set_failed(f"ReAct循环结束但无终态(status={agent.status})")
            yield agent._step_emitter.emit(FinalStep(
                step=agent.llm_call_count,
                response=f"ReAct循环结束但无终态(status={agent.status})",
                thought="",
            ))

    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        error_step = handle_react_error(agent, e, agent.llm_call_count)
        yield agent._step_emitter.emit(error_step)

    finally:
        failed_step = _ensure_failed_final_step(agent)
        if failed_step:
            yield agent._step_emitter.emit(failed_step)
        _finalize_cycle(agent)
