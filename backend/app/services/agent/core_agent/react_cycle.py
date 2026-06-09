# -*- coding: utf-8 -*-
"""
run_react_cycle — ReAct 循环核心

逻辑流程:
1. initialize_run_state — 初始化状态
2. while steps < max_steps:
   a. _call_llm → LLM响应
   b. parse_llm_response → 解析为dict
   c. 根据type产出Step并yield
   d. action → _execute_tool → 追加observation
3. final → yield final step

小健 2026-06-08
P2-5: if/elif → 注册式分派 — 小欧 2026-06-08
F4修复: _handle_action拆分SRP + _call_llm空保护 + step_counter用int — 小欧 2026-06-08
P3-12: 删除3个纯透传函数(内联调用) — 小沈 2026-06-09
"""
import asyncio
from typing import Any, Dict, Optional
from collections import OrderedDict

from app.utils.logger import logger
from app.services.agent.llm_response_parser import parse_llm_response
from app.services.agent.steps import (
    StartStep, ThoughtStep, ActionToolStep,
    ObservationStep, FinalStep, ErrorStep,
    ChunkStep,
)
from app.services.agent.types import AgentStatus
from app.services.agent.agent_utils.message_utils import build_observation_text

# 敏感字段列表（脱敏用）— 小沈 2026-06-09
_SENSITIVE_FIELDS = {"password", "token", "api_key", "secret", "authorization", "credential"}



def _update_message_builder(agent, result, tool_name: str = "", tool_params: Dict = None):
    """更新message_builder — 小沈 2026-06-09"""
    if not hasattr(agent, 'message_builder') or not agent.message_builder:
        logger.warning("[react_cycle] message_builder不存在，跳过observation记录")
        return

    obs_text = build_observation_text(result, tool_name, tool_params or {})
    llm_call_count = getattr(agent, 'llm_call_count', 0)
    agent.message_builder.add_observation(obs_text, llm_call_count=llm_call_count)


async def _handle_action(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理action类型 — 支持多tool_calls并行执行 — 小沈 2026-06-09
    P2-02修复: 删除_extract_action_params纯委托,直接内联 — 小沈 2026-06-09
    """
    tool_name = parsed["tool_name"]
    tool_params = parsed.get("tool_params", {})
    pending_calls = parsed.get("_pending_calls", [])
    step = step_counter[0]

    all_calls = [{"tool_name": tool_name, "tool_params": tool_params}]
    all_calls.extend(pending_calls)
    is_parallel = len(all_calls) > 1

    # 1. 发射thought
    yield agent._step_emitter.emit(ThoughtStep(
        step=step,
        content=parsed.get("thought", ""),
        tool_name=tool_name,
        tool_params=tool_params,
        thought=parsed.get("thought", ""),
        reasoning=parsed.get("reasoning", ""),
    ))

    # 2. Layer 2+3安全检查 — 先检查再发射action — 小沈 2026-06-09
    from app.services.safety.tool_safety_checker import get_tool_safety_checker
    from app.api.v1.chat.confirm_operation import create_confirmation, wait_for_confirmation_result
    from app.services.agent.steps import IncidentStep
    
    safety_checker = get_tool_safety_checker()
    
    for call in all_calls:
        safety_result = safety_checker.check_before_execute(call["tool_name"], call["tool_params"])
        
        # 被拦截的操作（优先级最高）
        if safety_result.get("blocked"):
            yield agent._step_emitter.emit(ErrorStep(
                step=step,
                error_type="blocked",
                error_message=safety_result["message"]
            ))
            return
        
        # 需要确认的操作
        if safety_result.get("requires_confirmation"):
            # 脱敏参数
            desensitized_params = {k: v for k, v in call["tool_params"].items() 
                                   if k not in _SENSITIVE_FIELDS}
            
            # 先创建确认请求，获取confirm_id
            confirm_id = await create_confirmation(agent.task_id)
            
            # 发射authorization_required事件，携带confirm_id
            yield agent._step_emitter.emit(IncidentStep(
                step=step,
                incident_value="authorization_required",
                message=f"需要用户确认工具执行: {call['tool_name']}",
                data={
                    "confirm_id": confirm_id,
                    "tool_name": call["tool_name"],
                    "params": desensitized_params,
                    "safety_level": safety_result["safety_level"],
                },
            ))
            
            # 等待用户确认结果
            auth = await wait_for_confirmation_result(confirm_id, timeout=60)
            
            if not auth.get("confirmed"):
                yield agent._step_emitter.emit(ErrorStep(
                    step=step,
                    error_type="user_rejected",
                    error_message=f"用户拒绝执行工具: {call['tool_name']}"
                ))
                return
            
            # TODO: Session Trust机制（待实施）
            # if auth.get("trust_session"):
            #     session_trust.add_trust(agent.task_id, call["tool_name"], call["tool_params"])

    # 3. 安全检查通过，发射所有action步骤
    action_steps = []
    for call in all_calls:
        action_step = ActionToolStep(
            step=step,
            tool_name=call["tool_name"],
            tool_params=call["tool_params"],
        )
        action_steps.append(action_step)
        yield agent._step_emitter.emit(action_step)

    # 4. 执行工具调用
    if is_parallel:
        tasks = [agent._execute_tool(c["tool_name"], c["tool_params"]) for c in all_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        result = await agent._execute_tool(tool_name, tool_params)
        results = [result]

    # 4. 注入execution_result到action_step — P1-03修复
    for action_step, result in zip(action_steps, results):
        action_step._execution_result = result

    # 5. 构建observation — P1-04: 注入完整字段 + P2-18: 空值保护
    obs_parts = []
    for call, result in zip(all_calls, results):
        if isinstance(result, Exception):
            obs_text = f"Observation: 工具{call['tool_name']}执行异常: {result}"
            agent._update_executed_tool_summary(call["tool_name"], {"code": "error", "message": str(result)}, call["tool_params"])
        else:
            obs_text = build_observation_text(result, call["tool_name"], call["tool_params"])
            agent._update_executed_tool_summary(call["tool_name"], result, call["tool_params"])
        obs_parts.append(obs_text)
        # P2-17修复: 异常保护
        try:
            _update_message_builder(agent, result if not isinstance(result, Exception) else {"code": "error"}, tool_name=call["tool_name"], tool_params=call["tool_params"])
        except Exception as e:
            logger.warning(f"[react_cycle] _update_message_builder异常: {e}")

    # P2-18修复: obs_parts空值保护
    if not obs_parts:
        obs_parts = ["Observation: 无结果"]

    merged_obs = "\n\n".join(obs_parts) if len(obs_parts) > 1 else obs_parts[0]

    # P1-04修复: 注入完整字段到ObservationStep
    first_result = results[0] if results else {}
    yield agent._step_emitter.emit(ObservationStep(
        step=step + 1,
        observation=merged_obs,
        tool_name=tool_name if not is_parallel else f"{tool_name}+{len(pending_calls)}",
        tool_params=tool_params,
        execution_status=first_result.get("code", "") if isinstance(first_result, dict) else "",
        code=first_result.get("code", "") if isinstance(first_result, dict) else "",
        warning=first_result.get("warning") if isinstance(first_result, dict) else None,
        attachment=first_result.get("attachment") if isinstance(first_result, dict) else None,
        next_actions=first_result.get("next_actions") if isinstance(first_result, dict) else None,
    ))

    agent.message_builder.add_assistant(llm_response)


async def _handle_answer(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理answer/implicit类型"""
    step = step_counter[0]
    content = parsed.get("content", "") or llm_response.strip()
    thought = parsed.get("thought", content)
    reasoning = parsed.get("reasoning", "")

    if thought:
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=thought, thought=thought, reasoning=reasoning,
        ))

    yield agent._step_emitter.emit(FinalStep(
        step=step, response=content, thought=thought,
    ))
    agent.status = AgentStatus.COMPLETED


async def _handle_chunk_buffer_promotion(agent, step: int, content: str, chunk_buffer, step_counter: list):
    """处理chunk buffer提升 — 小沈 2026-06-08"""
    if not chunk_buffer:
        return

    chunk_buffer.append(content)
    if not chunk_buffer.should_promote():
        return

    accumulated = chunk_buffer.flush()
    if not accumulated:
        return

    yield agent._step_emitter.emit(ThoughtStep(
        step=step, content=f"Accumulated {len(accumulated)} chunks",
    ))
    yield agent._step_emitter.emit(ChunkStep(
        step=step, content=accumulated,
    ))


async def _handle_chunk(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理chunk类型 — 小沈 2026-06-08 重构"""
    step = step_counter[0]
    content = parsed.get("content", llm_response.strip())

    yield agent._step_emitter.emit(ChunkStep(step=step, content=content, is_reasoning=False))

    async for event in _handle_chunk_buffer_promotion(agent, step, content, chunk_buffer, step_counter):
        yield event


async def _handle_parse_error(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理parse_error类型"""
    yield agent._step_emitter.exit_with_error(
        step=step_counter[0], error_type="parse_error",
        error_message=parsed.get("error", "Unknown parse error"),
    )
    agent.status = AgentStatus.FAILED


async def _handle_unknown(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理未知类型"""
    yield agent._step_emitter.exit_with_error(
        step=step_counter[0], error_type="unknown_parse_type",
        error_message=f"Unknown parsed type: {parsed.get('type', 'unknown')}",
    )
    agent.status = AgentStatus.FAILED


_TYPE_HANDLERS: OrderedDict[str, callable] = OrderedDict([
    ("action", _handle_action),
    ("answer", _handle_answer),
    ("implicit", _handle_answer),
    ("chunk", _handle_chunk),
    ("parse_error", _handle_parse_error),
])
_DEFAULT_HANDLER = _handle_unknown


async def _process_single_step(agent, step_counter: list, chunk_buffer) -> bool:
    """处理单步循环 — 返回是否应该继续 — 小沈 2026-06-09 支持流式chunk"""
    step_counter[0] += 1

    llm_response = None
    async for chunk_or_response in agent._call_llm():
        chunk_type, chunk_data = chunk_or_response
        
        if chunk_type == "chunk":
            # 流式输出chunk给前端
            yield agent._step_emitter.emit(chunk_data)
        elif chunk_type == "response":
            # 完整响应
            llm_response = chunk_data

    if not llm_response or not isinstance(llm_response, str):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        yield agent._step_emitter.exit_with_error(
            step=step_counter[0], error_type="empty_response",
            error_message="LLM返回空响应",
        )
        agent.status = AgentStatus.FAILED
        return

    if agent._cancelled:
        yield agent._create_cancelled_chunk()
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


async def run_react_cycle(
    agent,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
):
    """ReAct循环:调用LLM→解析→执行工具→产出Step — 小沈 2026-06-08 重构"""
    from app.config import get_config
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    chunk_buffer = agent._initialize_run_state(task, task_id, context)

    step_counter = [0]
    agent.status = AgentStatus.RUNNING

    try:
        while step_counter[0] < max_steps:
            async for event in _process_single_step(agent, step_counter, chunk_buffer):
                yield event

            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
                break

            # R10-4修复: chunk累积超时强制停止,防止LLM持续返回chunk导致无限循环 — 小沈 2026-06-09
            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({step_counter[0]}步),强制停止")
                agent.status = AgentStatus.COMPLETED
                break

    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        yield agent._step_emitter.exit_with_error(
            step=step_counter[0], error_type="runtime_error", error_message=str(e),
        )
        agent.status = AgentStatus.FAILED

    finally:
        agent._on_after_loop()
        agent._complete_tracked_task(agent.status == AgentStatus.COMPLETED)
