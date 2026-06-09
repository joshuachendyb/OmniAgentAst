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
    P2-02修复: 拆分职责为独立函数
    """
    tool_name, tool_params = _extract_action_params(parsed)
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

    # 2. 发射所有action步骤 — P1-03: 保留引用用于后续注入execution_result
    action_steps = []
    for call in all_calls:
        action_step = ActionToolStep(
            step=step,
            tool_name=call["tool_name"],
            tool_params=call["tool_params"],
        )
        action_steps.append(action_step)
        yield agent._step_emitter.emit(action_step)

    # 3. 执行工具调用
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


def _emit_chunk_step(agent, step: int, content: str, is_reasoning: bool = False):
    """产出chunk步骤 — 小沈 2026-06-08 内联调用 — 小沈 2026-06-09"""
    # 保留供直接调用: agent._step_emitter.emit(ChunkStep(...))
    pass


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
    """处理单步循环 — 返回是否应该继续 — 小沈 2026-06-08"""
    step_counter[0] += 1

    llm_response = await agent._call_llm()

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

    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        yield agent._step_emitter.exit_with_error(
            step=step_counter[0], error_type="runtime_error", error_message=str(e),
        )
        agent.status = AgentStatus.FAILED

    finally:
        agent._on_after_loop()
        agent._complete_tracked_task(agent.status == AgentStatus.COMPLETED)
