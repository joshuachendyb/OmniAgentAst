# -*- coding: utf-8 -*-
"""
Agent 模块

小沈 - 2026-06-08 清理死代码
小欧 - 2026-07-10 扁平化 core_agent/
"""

from .base_agent import BaseAgent
from .react_loop import run_react_cycle  # 8.4拆分: react_cycle.py移交main循环给react_loop — 小健 2026-09-05
__all__ = [
    "BaseAgent",
    "run_react_cycle",
]
