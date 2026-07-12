# -*- coding: utf-8 -*-
"""
run_react_cycle — ReAct 循环核心（薄调度）

职责: 循环调度 + 类型分派 + 状态推断，不含业务逻辑
业务逻辑在 handlers/ 目录

chendyg 2026-07-01: 状态集中管理重构v2
- 状态用 status_table，数据 handler 自己写
- _dispatch_handler 基于 event type 推断状态
- handler 保留 add_observation/add_assistant_message，不绕路
"""

import asyncio
import time
from typing import Any, Dict, Optional, AsyncGenerator

from app.logger import logger
from app.services.llm.error_classifier import SystemErrorClassifier
from app.logger.prompt_logger import get_prompt_logger
from app.config import get_config
from app.services.agent.steps import ChunkStep, FinalStep, ObservationStep, ErrorStep
from app.services.agent.status_table import AgentStatus, set_status, set_failed, set_completed, set_cancelled
from app.services.agent.initialize_run_state import initialize_run_state
from app.services.agent.handlers import (
    handle_action, handle_answer,
)
from app.services.agent.llm_stream import call_llm_with_fallback
from app.services.agent.tool_cache_manager import get_openai_tools

_MAX_CONSECUTIVE_TRUNCATIONS = 3


def handle_react_error(agent, error, step):
    """统一处理ReAct循环中的错误 — 只创建 ErrorStep，不设状态 — chendyg 2026-07-01"""
    error_type = SystemErrorClassifier.classify_error(error).name.lower()
    logger.error(f"[ErrorHandler] 错误类型={error_type}: {error}")
    recoverable = _is_recoverable_error(error)
    return ErrorStep(step=step, error_type=error_type, error_message=str(error), recoverable=recoverable)


def _is_recoverable_error(error) -> bool:
    """判断错误是否可恢复（FC格式错误/网络错误/超时） — chendyg 2026-07-01"""
    try:
        from app.services.llm.core import FCFormatError
        if isinstance(error, FCFormatError):
            return True
    except ImportError:
        pass
    if isinstance(error, asyncio.TimeoutError):
        return True
    try:
        import httpx
        if isinstance(error, (
            httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError,
            httpx.ProxyError, httpx.TooManyRedirects,
        )):
            return True
    except ImportError:
        pass
    return False


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
            for j in range(i + 1, len(history)):
                next_msg = history[j]
                if next_msg.get("role") in ("tool", "observation"):
                    return False
            return True
    return False


async def _dispatch_handler(agent, llm_response):
    """按type分派handler，基于 event type + recoverable 推断状态 — chendyg 2026-07-01
    
    状态推断规则:
    - "error" + recoverable → 置RETRYING（重试由编排层except块处理）；"error" + !recoverable → set_failed
    - "error" + !recoverable → set_failed
    - "final" → set_completed
    - 其他 → continue（不设状态）
    """
    parsed_type = llm_response.get("type", "answer")
    step = agent.llm_call_count
    thought = llm_response.get("thought", "")
    reasoning = llm_response.get("reasoning", "")
    if thought:
        reasoning_part = f"\n{time.strftime('%H:%M:%S')} === 推理 ===\n{reasoning}" if reasoning else ""
        print(f"{time.strftime('%H:%M:%S')} [Thought] step={step}, {thought}{reasoning_part}")  # 小欧 2026-07-02 控制台
    if parsed_type == "action":
        handler = handle_action(agent, llm_response)
    else:
        handler = handle_answer(agent, llm_response)

    seen_types = set()
    last_event = None
    last_error_event = None
    async for event in handler:
        seen_types.add(event.type)
        last_event = event
        if event.type == "error":
            last_error_event = event
        yield event

    if "error" in seen_types:
        error_event = last_error_event
        error_msg = error_event.get_content() if hasattr(error_event, 'get_content') else ""
        if getattr(error_event, 'recoverable', False):
            set_status(agent, AgentStatus.RETRYING, error_msg)
        else:
            set_failed(agent, error_msg)
    elif "final" in seen_types:
        set_completed(agent)


def _ensure_failed_final_step(agent):
    """FAILED时补发FinalStep — 小健 2026-06-17 从finally提取
    response="" 触发前端空响应守卫，设置 isError=true + 用户友好错误消息 — chendyg 2026-06-30"""
    if agent.status != AgentStatus.FAILED:
        return
    return FinalStep(
        step=agent.llm_call_count,
        response="",
        thought="",
    )


def _finalize_cycle(agent):
    """循环后收尾: 状态回调+任务追踪 — 小健 2026-06-17 从finally提取"""
    agent._on_after_loop()
    agent._step_emitter.complete_task(agent.status == AgentStatus.COMPLETED)


async def _process_single_step(agent, chunk_buffer) -> AsyncGenerator:
    """单步ReAct调度: LLM调用→响应处理→分发 — 小欧 2026-06-25 / 小欧 2026-07-09 加分区注释"""

    # ── Phase 1: LLM 调用准备 ──────────────────────────────────
    agent.llm_call_count += 1
    agent.message_builder.trim_history()  # 唯一裁剪入口 — 小欧 2026-07-01
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

    # ── Phase 2: LLM 流式调用 ──────────────────────────────────
    llm_response = None
    async for chunk_or_response in call_llm_with_fallback(agent, messages, openai_tools):
        chunk_type, chunk_data = chunk_or_response

        if chunk_type == "chunk":
            content = chunk_data.content if hasattr(chunk_data, 'content') else str(chunk_data)
            is_reasoning = getattr(chunk_data, 'is_reasoning', False)
            chunk_buffer.append(content)
            chunk_step = ChunkStep(
                step=agent.llm_call_count,
                content=content,
                is_reasoning=is_reasoning,
            )
            yield agent._step_emitter.emit(chunk_step)
        elif chunk_type == "response":
            llm_response = chunk_data
            chunk_buffer.clear()

    # ── Phase 3: 响应分发 ──────────────────────────────────────
    set_status(agent, AgentStatus.EXECUTING)

    step = agent.llm_call_count

    # ── 场景A: 空响应 — LLM未返回有效数据 ──────────────────────
    if not llm_response or not isinstance(llm_response, dict):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, empty_response")  # 小欧 2026-07-02 控制台
        set_failed(agent, "LLM返回空响应")
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="empty_response",
            error_message="LLM返回空响应"
        ))
        return

    # ── 场景B: 任务取消 ─────────────────────────────────────────
    if getattr(getattr(agent, 'llm_client', None), '_cancelled', False):
        print(f"{time.strftime('%H:%M:%S')} [Cancel] step={step}, cancelled")  # 小欧 2026-07-02 控制台
        yield agent._create_cancelled_chunk()
        yield agent._step_emitter.emit(FinalStep(
            step=step,
            response="任务已被中断",
            thought="",
        ))
        set_cancelled(agent)
        return

    # ── 场景C: LLM直接回答 → 注入复核warning（不重试）— 小健 2026-07-03
    # 设计: fall through到正常分发, warning进history,
    # 下轮循环LLM会看到这条observation并重新思考 — 小欧 2026-07-09
    if (llm_response.get("type") == "answer"
            and llm_response.get("content")):
        has_tool_results = any(
            msg.get("role") == "tool"
            for msg in agent.message_builder.conversation_history
        )
        if not has_tool_results:
            content = llm_response.get("content", "")
            logger.warning(f"[B3] LLM返回answer但未调用任何工具(step={step})")
            obs_text = "[Observation] 警告: 你未调用任何工具-->必须复核3遍用户任务:[1]问答任务补充说明;[2] 多步任务就继续调用工具"
            agent.message_builder.add_observation(
                obs_text, {"tool_call_id": "", "tool_calls": [], "llm_content": content},
            )

    # ── 场景D: 输出截断重试 — 检测preamble截断,注入重试observation ── 小健 2026-07-03
    if _should_retry_truncated_tool(agent, llm_response):
        content = llm_response.get("content", "")
        agent._consecutive_truncations = getattr(agent, '_consecutive_truncations', 0) + 1
        logger.warning(f"[run_react_cycle] 检测到LLM输出截断(step={step}, 连续第{agent._consecutive_truncations}次, content={content[:50]})")

        if agent._consecutive_truncations >= _MAX_CONSECUTIVE_TRUNCATIONS:
            logger.error(f"[run_react_cycle] LLM连续截断{_MAX_CONSECUTIVE_TRUNCATIONS}次, 停止重试, 设为FAILED")
            print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, consecutive_truncation")  # 小欧 2026-07-02 控制台
            set_failed(agent, f"LLM连续{_MAX_CONSECUTIVE_TRUNCATIONS}次输出截断")
            yield agent._step_emitter.emit(FinalStep(
                step=step,
                response=f"LLM连续{_MAX_CONSECUTIVE_TRUNCATIONS}次输出截断",
                thought="",
            ))
            return

        obs_text = "[Observation] 工具调用输出不完整，请重新调用该工具并补充完整参数"
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
            llm_data=[{"summary": "LLM工具调用输出截断", "action": {}, "status": {"exec_code": "error", "message": obs_text}}],
            tool_result={},
        ))
        return

    # ── 场景E: 正常分发 ─────────────────────────────────────────
    agent._consecutive_truncations = 0
    async for event in _dispatch_handler(agent, llm_response):
        yield event


async def run_react_cycle(
    agent,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
):
    """ReAct循环:调用LLM→解析→分派handler→产出Step — chendyg 2026-07-01 状态集中管理重构v2"""
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    chunk_buffer = initialize_run_state(agent, task, task_id, context)

    if max_steps <= 0:
        logger.warning(f"[run_react_cycle] max_steps={max_steps}, 直接设为FAILED")
        set_failed(agent, f"max_steps={max_steps}, 无可用步骤")
        yield agent._step_emitter.emit(FinalStep(
            step=0, response=f"max_steps={max_steps}, 无可用步骤", thought="",
        ))
        _finalize_cycle(agent)
        return

    try:
        while agent.llm_call_count < max_steps:
            async for event in _process_single_step(agent, chunk_buffer):
                yield event

            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED):
                break

            # ======== RETRYING 处理（react循环重试）========
            # 说明：本态是"可恢复错误后的重试中间态"。llm_call_count 已+1，
            # react循环回 THINKING 重新调用LLM（即第N次重试），并非原地重跑当前step。
            # 与 tool_retry_engine 的"工具级重试"（同工具重执行）及 base_service 的
            # HTTP请求重试是两套独立机制，勿混淆。 — 小欧 2026-07-12 修正矛盾注释
            if agent.status == AgentStatus.RETRYING:
                agent._retry_count = getattr(agent, '_retry_count', 0) + 1
                if agent._retry_count > 3:
                    set_failed(agent, "可恢复错误重试超限")
                    break
                set_status(agent, AgentStatus.THINKING, f"第{agent._retry_count}次重试")
            elif agent.status == AgentStatus.EXECUTING:
                set_status(agent, AgentStatus.THINKING)

            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({agent.llm_call_count}步),强制停止")
                set_failed(agent, f"chunk累积超时({agent.llm_call_count}步)")
                yield agent._step_emitter.emit(ErrorStep(step=agent.llm_call_count, error_type="chunk_buffer_timeout", error_message="chunk buffer累积超时，强制停止"))
                break

        if agent.status not in (
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
        ):
            logger.warning(f"[run_react_cycle] 循环结束无终态(status={agent.status}), 设为FAILED")
            set_failed(agent, f"ReAct循环结束但无终态(status={agent.status})")
            yield agent._step_emitter.emit(FinalStep(
                step=agent.llm_call_count,
                response=f"ReAct循环结束但无终态(status={agent.status})",
                thought="",
            ))

    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        error_step = handle_react_error(agent, e, agent.llm_call_count)
        yield agent._step_emitter.emit(error_step)
        if hasattr(error_step, 'recoverable') and error_step.recoverable:
            agent._retry_count = getattr(agent, '_retry_count', 0) + 1
            if agent._retry_count > 3:
                set_failed(agent, f"重试超限: {e}")
            else:
                set_status(agent, AgentStatus.RETRYING, str(e)[:200])
        else:
            set_failed(agent, f"循环异常: {e}"[:200])

    finally:
        failed_step = _ensure_failed_final_step(agent)
        if failed_step:
            yield agent._step_emitter.emit(failed_step)
        _finalize_cycle(agent)
