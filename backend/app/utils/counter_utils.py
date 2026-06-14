# -*- coding: utf-8 -*-
"""
counter_utils — 步骤计数器工具

从 time_utils.py 移出,SRP: 计数器与时间无关
Author: 小欧 - 2026-06-08
"""

from typing import Callable


def create_step_counter() -> Callable[[], int]:
    """
    创建统一的步骤计数器函数

    Returns:
        返回一个闭包函数,每次调用返回递增的步骤号(从1开始)
    """
    step_counter = 0

    def next_step() -> int:
        nonlocal step_counter
        step_counter += 1
        return step_counter

    return next_step


__all__ = ["create_step_counter"]
