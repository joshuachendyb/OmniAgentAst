# -*- coding: utf-8 -*-
"""
工具查询辅助函数 — 从注册表查询工具实现

小沈 - 2026-06-08 删除死代码: get_implementations_from_registry, get_tools_from_file_registry
"""

from typing import Dict, Callable
from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory


def get_tools_from_registry_by_category(category: ToolCategory) -> Dict[str, Callable]:
    """
    按分类从registry获取工具(一次遍历,消除N+1查询)
    
    Args:
        category: 工具分类
    
    Returns:
        {工具名: 工具函数} 格式
    """
    return tool_registry.get_implementations_by_category(category)
