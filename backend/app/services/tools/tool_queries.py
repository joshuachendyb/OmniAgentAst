# -*- coding: utf-8 -*-
"""
工具查询辅助函数 — 从注册表查询工具实现

小沈 - 2026-06-08 删除死代码: get_implementations_from_registry, get_tools_from_file_registry
F4修复: 消除对registry.py的直接import(脆皮依赖) — 小欧 2026-06-08
"""

from typing import Dict, Callable
from app.services.tools.tool_types import ToolCategory


def get_tools_from_registry_by_category(
    registry,
    category: ToolCategory
) -> Dict[str, Callable]:
    """
    按分类从registry获取工具(一次遍历,消除N+1查询)

    Args:
        registry: ToolRegistry实例(外部传入,避免直接import)
        category: 工具分类

    Returns:
        {工具名: 工具函数} 格式
    """
    return registry.get_implementations_by_category(category)
