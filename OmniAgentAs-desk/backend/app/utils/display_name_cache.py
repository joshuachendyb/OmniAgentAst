"""
display_name 缓存模块

用于在保存AI回复时，自动获取当时使用的模型显示名称
支持模型切换：每次新的流式响应都会更新缓存中的最新值

创建时间: 2026-03-03
编写人: 小沈
"""

from typing import Dict, Optional
from app.utils.logger import logger

# ⭐ 缓存机制：存储 session_id 到 display_name 的映射
display_name_cache: Dict[str, str] = {}


def cache_display_name(session_id: str, display_name: str):
    """
    缓存 session_id 对应的 display_name
    
    Args:
        session_id: 会话ID
        display_name: 模型显示名称（如 "OpenAI (GPT-4)"）
    """
    display_name_cache[session_id] = display_name
    logger.debug(f"缓存 display_name: session_id={session_id}, display_name={display_name}")


def get_cached_display_name(session_id: str) -> Optional[str]:
    """
    从缓存中获取 session_id 对应的 display_name
    
    Args:
        session_id: 会话ID
        
    Returns:
        缓存的 display_name，如果没有则返回 None
    """
    display_name = display_name_cache.get(session_id)
    logger.debug(f"获取缓存 display_name: session_id={session_id}, display_name={display_name}")
    return display_name
