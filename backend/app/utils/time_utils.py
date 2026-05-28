# -*- coding: utf-8 -*-
"""
时间工具函数 — 统一时间戳/步骤计数器入口

【小健 2026-05-28】SRP+DRY：从chat_helpers.py提取集中到此，
所有create_timestamp/create_step_counter调用方统一从此处导入。

Author: 小健 - 2026-05-28
"""

from datetime import datetime
from typing import Callable


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


__all__ = [
    "create_timestamp",
    "create_step_counter",
]
