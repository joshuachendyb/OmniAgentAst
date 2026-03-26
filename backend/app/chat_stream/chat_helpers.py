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


def get_provider_display_name(provider: str) -> str:
    """
    直接返回provider名称，不做任何映射转换
    只验证provider是否在配置文件中存在
    """
    from app.config import get_config
    config = get_config()
    ai_config = config.get('ai', {})
    
    # 如果provider在配置文件中存在，直接返回原始名称
    if provider in ai_config:
        return provider
    else:
        return provider


def create_final_response(
    content: str,
    model: str,
    provider: str,
    display_name: Optional[str] = None,
    step: Optional[int] = None
) -> str:
    """
    创建统一的 final 响应格式
    
    Args:
        content: 最终内容
        model: 模型名称
        provider: 提供商
        display_name: 显示名称（可选）
        step: 步骤号
    
    Returns:
    SSE 格式的 final 响应字符串
    """
    response = {
        'type': 'final',
        'content': content,
        'display_name': display_name if display_name else f"{provider} ({model})" or None,
        'timestamp': create_timestamp(),
    }
    if step is not None:
        response['step'] = step
    return f"data: {json.dumps(response)}\n\n"
