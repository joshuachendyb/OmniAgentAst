"""
display_name 缓存模块

用于在保存AI回复时，自动获取当时使用的模型显示名称
支持模型切换：每次新的流式响应都会更新缓存中的最新值

创建时间: 2026-03-03
编写人: 小沈
更新: 2026-03-04 小健 - 添加线程安全和缓存清理机制
重构: 2026-05-31 小健 - 改用LRUCache，消除自造缓存（问题6修复）
"""

from typing import Optional
from app.utils.logger import logger
from app.utils.cache import LRUCache
from app.constants import MAX_CACHE_SIZE

# 使用LRUCache替代自造dict+Lock缓存
_cache = LRUCache(max_size=MAX_CACHE_SIZE)


def cache_display_name(session_id: str, display_name: str):
    """
    缓存 session_id 对应的 display_name
    
    Args:
        session_id: 会话ID
        display_name: 模型显示名称（如 "OpenAI (GPT-4)"）
    """
    _cache.set(session_id, display_name)
    logger.debug(f"缓存 display_name: session_id={session_id}, display_name={display_name}")


def get_cached_display_name(session_id: str) -> Optional[str]:
    """
    从缓存中获取 session_id 对应的 display_name
    
    Args:
        session_id: 会话ID
        
    Returns:
        缓存的 display_name，如果没有则返回 None
    """
    display_name = _cache.get(session_id)
    logger.debug(f"获取缓存 display_name: session_id={session_id}, display_name={display_name}")
    return display_name


def clear_cached_display_name(session_id: str):
    """
    清除指定会话的缓存
    
    Args:
        session_id: 会话ID
    """
    _cache.delete(session_id)
    logger.debug(f"清除缓存 display_name: session_id={session_id}")
