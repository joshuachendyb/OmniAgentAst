# -*- coding: utf-8 -*-
"""
answer_handler — answer/implicit类型处理

从react_cycle.py拷出_handle_answer函数，保持业务逻辑不变

Author: 小沈 - 2026-06-09
"""
from typing import Dict

from app.services.agent.steps import ThoughtStep, FinalStep
from app.services.agent.types import AgentStatus


async def handle_answer(agent, parsed: Dict, chunk_buffer):
    """处理answer类型 — FC-only: 空内容视为错误"""
    step = agent.llm_call_count
    content = parsed.get("content", "")

    if not content:
        from app.utils.logger import logger
        logger.warning(f"[handle_answer] LLM返回空内容(step={step})")
        yield agent._step_emitter.exit_with_error(
            step_count=step, error_type="empty_answer",
            error_message="LLM返回空内容",
        )
        agent.status = AgentStatus.FAILED
        return

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