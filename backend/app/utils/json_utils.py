# -*- coding: utf-8 -*-
"""
通用数据处理函数 — 小健 2026-05-28

【公共函数规范】
本文件是公共utility模块,所有数据处理相关公共函数必须在此定义。
禁止在业务代码(api/v1/、services/等)中重复定义公共函数。

【小沈 2026-05-28】新增:safe_parse_json
【小沈 2026-05-29】重命名:safe_parse_json → parse_json(符合命名规范)
【小沈 2026-05-30】移除:safe_truncate → 移至 agent/tool_result_formatter.py 内部(唯一消费者)
【小沈 2026-06-08】新增:raise_on_error参数，统一所有JSON解析场景

Author: 小健 - 2026-05-28
"""

import json
from typing import Any, Optional


def parse_json(json_str: Optional[str], label: str = "", raise_on_error: bool = False) -> Any:
    """解析 JSON 字符串 — 小沈 2026-06-08 统一所有场景
    
    Args:
        json_str: JSON字符串
        label: 标签（用于日志）
        raise_on_error: True则抛异常，False则返回None
    
    Returns:
        解析结果或None（raise_on_error=False时）
    
    Raises:
        json.JSONDecodeError: raise_on_error=True且解析失败时
        TypeError: raise_on_error=True且传入None时
    """
    if not json_str:
        if raise_on_error:
            raise TypeError(f"{label}JSON字符串为空")
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        if raise_on_error:
            raise
        return None


def read_json_file(file_path: str, label: str = "", raise_on_error: bool = False) -> Any:
    """读取JSON文件 — 小沈 2026-06-17 新增公用函数
    
    Args:
        file_path: JSON文件路径
        label: 标签（用于日志）
        raise_on_error: True则抛异常，False则返回None
    
    Returns:
        解析结果或None（raise_on_error=False时）
    
    Raises:
        FileNotFoundError: raise_on_error=True且文件不存在时
        json.JSONDecodeError: raise_on_error=True且解析失败时
    """
    from pathlib import Path
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if raise_on_error:
            raise
        return None
    except json.JSONDecodeError:
        if raise_on_error:
            raise
        return None


__all__ = [
    "parse_json",
    "read_json_file",
]
