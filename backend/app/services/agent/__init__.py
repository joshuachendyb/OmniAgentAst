# -*- coding: utf-8 -*-
# 【拨乱反正 2026-05-28 小沈】session→task 命名修正
# 原则：绝不搞向后兼容，旧名必须彻底清除
"""
Agent 模块 - 多意图处理架构 + 文件操作服务

【合并时间】2026-03-21 小沈
【重构 2026-05-27 小欧】__getattr__懒加载移至 _deprecated_imports.py
"""

# ============================================================================
# 新框架导出（无循环依赖）
# ============================================================================
from .base_react import BaseAgent
from .generic_react import GenericReactAgent
from .tool_executor import ToolExecutor
from .llm_response_parser import parse_react_response
from .task_base import TaskServiceBase, TaskStatsMixin

# ============================================================================
# 原 file_operations 向后兼容（__getattr__懒加载）
# ============================================================================
from .task_service import TaskOperationService, get_task_service
from ._deprecated_imports import __getattr__


__all__ = [
    # 新框架
    "BaseAgent",
    "GenericReactAgent",
    "ToolExecutor",
    "TaskServiceBase",
    "TaskStatsMixin",
    "parse_react_response",
    # 新框架（task 服务）
    "TaskOperationService",
    "get_task_service",
    # 原 file_operations（通过__getattr__懒加载）
    "FileOperationSafety",
    "FileSafetyConfig",
    "get_file_safety_service",
    "FileTools",
    "get_file_tools",
]
