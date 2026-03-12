"""
display_name 缓存模块

用于在保存AI回复时，自动获取当时使用的模型显示名称
支持模型切换：每次新的流式响应都会更新缓存中的最新值

创建时间: 2026-03-03
编写人: 小沈
更新: 2026-03-04 小健 - 添加线程安全和缓存清理机制
"""

from typing import Dict, Optional
from threading import Lock
from app.utils.logger import logger

# ⭐ 缓存机制：存储 session_id 到 display_name 的映射
_display_name_cache: Dict[str, str] = {}
_cache_lock = Lock()  # 线程安全锁，防止并发访问冲突
_MAX_CACHE_SIZE = 1000  # 最大缓存条目数，防止内存泄漏


def cache_display_name(session_id: str, display_name: str):
    """
    缓存 session_id 对应的 display_name
    
    Args:
        session_id: 会话ID
        display_name: 模型显示名称（如 "OpenAI (GPT-4)"）
    """
    with _cache_lock:
        # 如果缓存超过大小限制，清理旧的条目
        if len(_display_name_cache) >= _MAX_CACHE_SIZE:
            # 简单策略：删除前一半的缓存条目
            keys_to_remove = list(_display_name_cache.keys())[:_MAX_CACHE_SIZE // 2]
            for key in keys_to_remove:
                del _display_name_cache[key]
            logger.debug(f"缓存清理：删除了 {len(keys_to_remove)} 个旧条目")
        
        _display_name_cache[session_id] = display_name
        logger.debug(f"缓存 display_name: session_id={session_id}, display_name={display_name}")


def get_cached_display_name(session_id: str) -> Optional[str]:
    """
    从缓存中获取 session_id 对应的 display_name
    
    Args:
        session_id: 会话ID
        
    Returns:
        缓存的 display_name，如果没有则返回 None
    """
    with _cache_lock:
        display_name = _display_name_cache.get(session_id)
        logger.debug(f"获取缓存 display_name: session_id={session_id}, display_name={display_name}")
        return display_name


def clear_cached_display_name(session_id: str):
    """
    清除指定会话的缓存
    
    Args:
        session_id: 会话ID
    """
    with _cache_lock:
        if session_id in _display_name_cache:
            del _display_name_cache[session_id]
            logger.debug(f"清除缓存 display_name: session_id={session_id}")


def clear_all_cache():
    """
    清除所有缓存（用于测试或重启）
    """
    with _cache_lock:
        _display_name_cache.clear()
        logger.info("已清除所有 display_name 缓存")
