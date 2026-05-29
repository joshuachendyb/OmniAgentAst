# -*- coding: utf-8 -*-
"""
时间工具函数 — 统一时间戳/步骤计数器入口

【公共函数规范】
本文件是公共utility模块，所有时间相关公共函数必须在此定义。
禁止在业务代码（api/v1/、services/等）中重复定义公共函数。

【小健 2026-05-28】SRP+DRY：从chat_helpers.py提取集中到此
【小沈 2026-05-28】新增：convert_to_utc/ensure_ts_milliseconds/get_timestamp_ms/get_utc_timestamp
【小沈 2026-05-29】重命名：ensure_ts_milliseconds → ensure_timestamp_milliseconds（符合命名规范）

Author: 小健 - 2026-05-28
"""

from datetime import datetime, timezone
from typing import Any, Callable


def create_timestamp() -> int:
    """生成统一的时间戳（毫秒）"""
    return int(datetime.now().timestamp() * 1000)


def get_timestamp_ms() -> int:
    """获取毫秒时间戳（UTC）"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def get_utc_timestamp() -> str:
    """获取UTC时间戳，ISO格式"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def convert_to_utc(time_value) -> str:
    """将时间转换为UTC ISO格式"""
    if not time_value:
        return get_utc_timestamp()
    if 'Z' in str(time_value) or '+' in str(time_value):
        return str(time_value)
    try:
        dt = datetime.fromisoformat(str(time_value).replace(' ', 'T'))
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.isoformat().replace("+00:00", "Z")
    except:
        return get_utc_timestamp()


def ensure_timestamp_milliseconds(ts_value: Any) -> int:
    """确保时间戳转为毫秒整数"""
    if isinstance(ts_value, (int, float)):
        return int(ts_value)
    try:
        return int(datetime.fromisoformat(str(ts_value).replace(' ', 'T')).timestamp() * 1000)
    except (ValueError, TypeError, OverflowError):
        return int(datetime.now(timezone.utc).timestamp() * 1000)


# 兼容旧名称
ensure_ts_milliseconds = ensure_timestamp_milliseconds


def create_step_counter() -> Callable[[], int]:
    """
    创建统一的步骤计数器函数

    Returns:
        返回一个闭包函数，每次调用返回递增的步骤号（从1开始）
    """
    step_counter = 0

    def next_step() -> int:
        nonlocal step_counter
        step_counter += 1
        return step_counter

    return next_step


__all__ = [
    "create_timestamp",
    "get_timestamp_ms",
    "get_utc_timestamp",
    "convert_to_utc",
    "ensure_timestamp_milliseconds",
    "ensure_ts_milliseconds",  # 兼容旧名称
    "create_step_counter",
]
