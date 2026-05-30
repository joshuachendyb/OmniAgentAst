# -*- coding: utf-8 -*-
"""
chat_stream共享辅助函数

创建时间: 2026-03-19
创建人: 小健
从chat_stream.py中提取的共享函数，供types模块使用
Updated: 小欧 - 2026-05-30 改用 FinalStep + format_agent_sse
"""

from typing import Optional

from app.utils.time_utils import create_timestamp, create_step_counter
from app.services.agent.steps import StepFactory
from app.chat_stream.sse_formatter import format_agent_sse


def create_final_response(
    content: str,
    step: Optional[int] = None,
    display_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    is_finished: bool = True,
    thought: str = '',
    is_streaming: bool = False,
    is_reasoning: bool = False
) -> str:
    """
    创建最终的SSE响应 — 使用 FinalStep + format_agent_sse
    
    Args:
        content: 最终回复内容
        step: 步骤序号（可选）
        display_name: 模型显示名称（可选）
        provider: 模型提供商（可选）
        model: 模型名称（可选）
        is_finished: 是否完成
        thought: 思考内容
        is_streaming: 是否流式输出
        is_reasoning: 是否在推理中
    
    Returns:
        SSE格式的响应字符串
    """
    final_step = StepFactory.create_final_step(
        step=step or 0,
        response=content,
        thought=thought,
        model=model,
        provider=provider
    )
    return format_agent_sse(final_step)
