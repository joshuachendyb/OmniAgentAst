# -*- coding: utf-8 -*-
# 【拨乱反正 2026-05-28 小沈】session→task 命名修正
# 原则：绝不搞向后兼容，旧名必须彻底清除
"""
Agent 模块 - 多意图处理架构 + 文件操作服务

【合并时间】2026-03-21 小沈
"""

# ============================================================================
# 新框架导出（无循环依赖）
# ============================================================================
from .base_react import BaseAgent
from .generic_react import GenericReactAgent
from .tool_executor import ToolExecutor
from .llm_response_parser import parse_react_response
__all__ = [
    # 新框架
    "BaseAgent",
    "GenericReactAgent",
    "ToolExecutor",
    "parse_react_response",
]
