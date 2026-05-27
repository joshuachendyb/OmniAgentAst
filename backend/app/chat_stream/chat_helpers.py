# backend/app/chat_stream_helpers.py
# chat_stream共享辅助函数
# 创建时间: 2026-03-19
# 创建人: 小健
# 从chat_stream.py中提取的共享函数，供types模块使用

from datetime import datetime
import json
from typing import Optional, Callable


def create_timestamp() -> int:
    """生成统一的时间戳（毫秒）"""
    return int(datetime.now().timestamp() * 1000)


def create_step_counter() -> Callable[[], int]:
    """
    创建统一的步骤计数器函数
    
    Returns:
        返回一个闭包函数，每次调用返回递增的步骤号（从1开始）
    
    Example:
        counter = create_step_counter()
        counter()  # 返回 1
        counter()  # 返回 2
        counter()  # 返回 3
    """
    step_counter = 0
    
    def next_step() -> int:
        nonlocal step_counter
        step_counter += 1
        return step_counter
    
    return next_step


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
    创建最终的SSE响应 — 委托给sse_formatter统一入口
    
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
    from app.chat_stream.sse_formatter import format_final_sse
    return format_final_sse(
        response=content,
        step=step,
        display_name=display_name,
        provider=provider,
        model=model,
        is_finished=is_finished,
        thought=thought,
        is_streaming=is_streaming,
        is_reasoning=is_reasoning
    )
