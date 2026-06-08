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
"""
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


def _extract_action_params(parsed: Dict) -> tuple:
    """提取action参数 — 小沈 2026-06-08"""
    tool_name = parsed["tool_name"]
    tool_params = parsed.get("tool_params", {})
    return tool_name, tool_params


async def _emit_thought_and_action(agent, step: int, tool_name: str, tool_params: Dict, parsed: Dict):
    """产出thought和action步骤 — 小沈 2026-06-08"""
    yield agent._step_emitter.emit(ThoughtStep(
        step=step,
        content=parsed.get("thought", ""),
        tool_name=tool_name,
        tool_params=tool_params,
        thought=parsed.get("thought", ""),
        reasoning=parsed.get("reasoning", ""),
    ))

    yield agent._step_emitter.emit(ActionToolStep(
        step=step,
        tool_name=tool_name,
        tool_params=tool_params,
    ))


async def _execute_and_emit_observation(agent, step: int, tool_name: str, tool_params: Dict):
    """执行工具并产出observation — 小沈 2026-06-08"""
    result = await agent._execute_tool(tool_name, tool_params)

    yield agent._step_emitter.emit(ObservationStep(
        step=step + 1,
        observation=str(result),
        tool_name=tool_name,
        tool_params={},
    ))


def _update_message_builder(agent, result):
    """更新message_builder — 小沈 2026-06-08"""
    if hasattr(agent, 'message_builder') and agent.message_builder:
        agent.message_builder.add_observation(observation_text=str(result))
    else:
        logger.warning("[react_cycle] message_builder不存在，跳过observation记录")


async def _handle_action(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理action类型 — 产出thought+action+observation — 小沈 2026-06-08 重构"""
    tool_name, tool_params = _extract_action_params(parsed)
    step = step_counter[0]
    result = None

    async for event in _emit_thought_and_action(agent, step, tool_name, tool_params, parsed):
        yield event

    async for event in _execute_and_emit_observation(agent, step, tool_name, tool_params):
        yield event
        if "observation" in str(type(event)):
            result = event.observation

    _update_message_builder(agent, result)
    step_counter[0] = step + 1


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
    """产出chunk步骤 — 小沈 2026-06-08"""
    return agent._step_emitter.emit(ChunkStep(step=step, content=content, is_reasoning=is_reasoning))


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
    
    next_step = step + 1
    step_counter[0] = next_step
    yield agent._step_emitter.emit(ThoughtStep(
        step=next_step, content=f"Accumulated {len(accumulated)} chunks",
    ))
    yield agent._step_emitter.emit(ChunkStep(
        step=next_step + 1, content=accumulated,
    ))


async def _handle_chunk(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理chunk类型 — 小沈 2026-06-08 重构"""
    step = step_counter[0]
    content = parsed.get("content", llm_response.strip())
    
    yield _emit_chunk_step(agent, step, content)
    
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
    self,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
):
    """ReAct循环:调用LLM→解析→执行工具→产出Step — 小沈 2026-06-08 重构"""
    from app.config import get_config
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    chunk_buffer, _ = self._initialize_run_state(task, task_id, context)

    step_counter = [0]
    self.status = AgentStatus.RUNNING

    try:
        while step_counter[0] < max_steps:
            async for event in _process_single_step(self, step_counter, chunk_buffer):
                yield event
            
            if self.status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
                break

    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        yield self._step_emitter.exit_with_error(
            step=step_counter[0], error_type="runtime_error", error_message=str(e),
        )
        self.status = AgentStatus.FAILED

    finally:
        self._on_after_loop()
        self._complete_tracked_task(self.status == AgentStatus.COMPLETED)
