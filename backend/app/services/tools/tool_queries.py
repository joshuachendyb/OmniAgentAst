# -*- coding: utf-8 -*-
"""
工具查询辅助函数 — 从注册表查询工具实现

拆分自 registry.py — 小沈 2026-05-29
"""

from typing import Dict, Callable
from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory



def get_implementations_from_registry() -> Dict[str, Callable]:
    """
    从tool_registry获取所有工具实现函数(一次调用,消除N+1查询)

    Returns:
        {工具名: 工具函数} 格式
    """
    return tool_registry.list_all_tools()


def get_tools_from_registry_by_category(category: ToolCategory) -> Dict[str, Callable]:
    """
    按分类从registry获取工具(一次遍历,消除N+1查询)
    
    Args:
        category: 工具分类
    
    Returns:
        {工具名: 工具函数} 格式
    """
    return tool_registry.get_implementations_by_category(category)


def get_tools_from_file_registry() -> Dict[str, Callable]:
    """从tool_registry获取file工具 — 委托共享函数(消除DRY 小健2026-05-31)"""
    return get_tools_from_registry_by_category(ToolCategory.FILE)

