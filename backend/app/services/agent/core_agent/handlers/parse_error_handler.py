# -*- coding: utf-8 -*-
"""
parse_error_handler — parse_error类型处理

Author: 小沈 - 2026-06-13
"""
from app.services.agent.types import AgentStatus


async def handle_parse_error(agent, parsed, chunk_buffer):
    """处理parse_error — FC-only: exit_with_error"""
    step = agent.llm_call_count
    yield agent._step_emitter.exit_with_error(
        step_count=step,
        error_type="parse_error",
        error_message=parsed.get("content", "无法解析的JSON"),
    )
    agent.status = AgentStatus.FAILED
