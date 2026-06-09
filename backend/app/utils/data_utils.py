# -*- coding: utf-8 -*-
"""
数据处理工具函数 — 小沈 2026-06-09

提供数据摘要、截断等通用功能
"""

from typing import Any


def safe_truncate(data: Any, limit: int = 100) -> Any:
    """安全截断数据 — 小沈 2026-05-29
    
    Args:
        data: 任意数据
        limit: 截断长度
    
    Returns:
        截断后的数据
    """
    if isinstance(data, str):
        return data[:limit] if len(data) > limit else data
    if isinstance(data, list):
        return data[:limit] if len(data) > limit else data
    if isinstance(data, dict):
        if len(data) > limit:
            keys = list(data.keys())[:limit]
            return {k: data[k] for k in keys}
    return data


def extract_data_summary(data: Any, max_chars: int = 60) -> str:
    """从数据提取摘要（通用函数）— 小沈 2026-06-09
    
    用途：日志、调试、状态汇总等场景
    
    Args:
        data: 任意数据
        max_chars: 最大字符数（默认60）
    
    Returns:
        摘要字符串
    
    Examples:
        >>> extract_data_summary("hello world")
        'hello world'
        >>> extract_data_summary({"name": "test", "count": 10})
        'name=test; count=10'
        >>> extract_data_summary([1, 2, 3])
        '[3项]'
    """
    if not data:
        return ""
    if isinstance(data, str):
        return data[:max_chars]
    if isinstance(data, dict):
        keys = list(data.keys())[:5]
        parts = []
        for k in keys:
            v = data[k]
            if isinstance(v, (str, int, float, bool)):
                parts.append(f"{k}={str(v)[:20]}")
            elif isinstance(v, list):
                parts.append(f"{k}=[{len(v)}项]")
            elif isinstance(v, dict):
                parts.append(f"{k}={{...}}")
        return "; ".join(parts)[:max_chars]
    if isinstance(data, list):
        return f"[{len(data)}项]"
    return ""


__all__ = [
    "safe_truncate",
    "extract_data_summary",
]