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
    step: Optional[int] = None,
    display_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> str:
    """
    创建最终的SSE响应【小沈修复2026-03-28】
    - 添加model和provider字段，和数据库保存一致
    
    Args:
        content: 最终回复内容
        step: 步骤序号（可选）
        display_name: 模型显示名称（可选）
        provider: 模型提供商（可选）
        model: 模型名称（可选）
    
    Returns:
        SSE格式的响应字符串
    """
    # 构建 display_name
    final_display_name = display_name
    if not final_display_name and provider and model:
        final_display_name = f"{provider} ({model})"
    elif not final_display_name and provider:
        final_display_name = provider
    elif not final_display_name and model:
        final_display_name = model
    
    response = {
        'type': 'final',
        'content': content,
        'display_name': final_display_name,
        'timestamp': create_timestamp(),
        'model': model,  # 和数据库保存一致
        'provider': provider,  # 和数据库保存一致
    }
    if step is not None:
        response['step'] = step
    return f"data: {json.dumps(response)}\n\n"
