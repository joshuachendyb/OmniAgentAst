# backend/app/chat_stream_helpers.py
# chat_stream共享辅助函数
# 创建时间: 2026-03-19
# 创建人: 小健
# 从chat_stream.py中提取的共享函数，供types模块使用

from datetime import datetime


def create_timestamp() -> int:
    """生成统一的时间戳（毫秒）"""
    return int(datetime.now().timestamp() * 1000)


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
