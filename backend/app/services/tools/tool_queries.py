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
    从tool_registry获取所有工具实现函数

    Returns:
        {工具名: 工具函数} 格式
    """
    tools_list = tool_registry.list_tools()
    tool_names = [t["name"] for t in tools_list if "name" in t]
    return {name: tool_registry.get_implementation(name)
            for name in tool_names}


def get_tools_from_registry_by_category(category: ToolCategory) -> Dict[str, Callable]:
    """
    按分类从registry获取工具
    参考: 文档5.3节+7.6节完整代码
    
    Args:
        category: 工具分类
    
    Returns:
        {工具名: 工具函数} 格式
    """
    tools_list = tool_registry.list_tools(category=category, include_metadata=False)
    tool_names = [t["name"] for t in tools_list if "name" in t]
    
    # Get implementations
    result = {}
    for name in tool_names:
        impl = tool_registry.get_implementation(name)
        if impl:
            result[name] = impl
    return result


def get_tools_from_file_registry() -> Dict[str, Callable]:
    """
    从tool_registry获取file工具
    
    Returns:
        {工具名: 工具函数} 格式
    """
    # 触发 file_register 注册（确保注册已执行）
    from app.services.tools.file import file_register
    
    # 直接使用全局 tool_registry 实例
    result = {}
    for name in _FILE_TOOL_NAMES:  # 已知工具名列表
        impl = tool_registry.get_implementation(name)
        if impl:
            result[name] = impl
    return result


# 已知file工具名列表（统一命名）
_FILE_TOOL_NAMES = [
    "read_file", "write_text_file", "read_media_file", "edit_file",
    "list_directory", "search_files", "grep_file_content", "rename_file",
    "archive_tool", "file_operation", "data_file_format"
]
