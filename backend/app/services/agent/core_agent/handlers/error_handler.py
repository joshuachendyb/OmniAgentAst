# -*- coding: utf-8 -*-
"""
error_handler — 错误类型处理

从react_cycle.py拷出_handle_parse_error和_handle_unknown函数，保持业务逻辑不变

Author: 小沈 - 2026-06-09
"""
from typing import Dict

from app.services.agent.types import AgentStatus


async def handle_parse_error(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理parse_error类型
    
    从react_cycle.py第240-246行拷出，保持业务逻辑不变
    """
    yield agent._step_emitter.exit_with_error(
        step_count=step_counter[0], error_type="parse_error",
        error_message=parsed.get("error", "Unknown parse error"),
    )
    agent.status = AgentStatus.FAILED


async def handle_unknown(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理未知类型
    
    从react_cycle.py第249-255行拷出，保持业务逻辑不变
    """
    yield agent._step_emitter.exit_with_error(
        step_count=step_counter[0], error_type="unknown_parse_type",
        error_message=f"Unknown parsed type: {parsed.get('type', 'unknown')}",
    )
    agent.status = AgentStatus.FAILED