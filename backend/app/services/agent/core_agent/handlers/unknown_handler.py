# -*- coding: utf-8 -*-
"""
unknown_handler — 未知类型处理

Author: 小沈 - 2026-06-13
"""
from app.services.agent.types import AgentStatus


async def handle_unknown(agent, parsed, chunk_buffer):
    """处理未知类型 — FC-only: exit_with_error"""
    step = agent.llm_call_count
    yield agent._step_emitter.exit_with_error(
        step_count=step,
        error_type="unknown_type",
        error_message="未知的LLM响应类型: " + str(parsed.get("type", "unknown")),
    )
    agent.status = AgentStatus.FAILED
