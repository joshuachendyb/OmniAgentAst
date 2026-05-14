"""
工具别名统一管理 - 小健 2026-05-14

设计原则：
- 所有工具别名在一个地方定义
- 各Agent使用统一解析方法
- 支持分类别名和全局别名

Author: 小健 - 2026-05-14
"""

from typing import Dict


# ===== 分类工具别名（在此统一定义）=====
CATEGORY_TOOL_ALIASES: Dict[str, Dict[str, str]] = {
    "file": {
        "create_dir": "create_directory",
        "list_dir": "list_directory",
        "delete_dir": "delete_directory",
        "rename_dir": "rename_directory",
    },
    # 其他分类的别名可以在这里添加
    # "shell": {...},
    # "network": {...},
}

# ===== 全局工具别名 = 所有分类别的并集 =====
GLOBAL_TOOL_ALIASES: Dict[str, str] = {}
for _cat_aliases in CATEGORY_TOOL_ALIASES.values():
    GLOBAL_TOOL_ALIASES.update(_cat_aliases)


def resolve_tool_alias(tool_name: str, category: str = None) -> str:
    """
    解析工具别名 - 统一入口
    
    优先级：
    1. 分类别名（如果有category）
    2. 全局别名
    
    Args:
        tool_name: 工具名（可能是别名）
        category: 工具分类（可选）
    
    Returns:
        实际工具名
    
    Example:
        >>> resolve_tool_alias("create_dir")
        'create_directory'
        >>> resolve_tool_alias("create_dir", "file")
        'create_directory'
    """
    # 1. 检查分类别名
    if category and category in CATEGORY_TOOL_ALIASES:
        category_aliases = CATEGORY_TOOL_ALIASES[category]
        if tool_name in category_aliases:
            return category_aliases[tool_name]
    
    # 2. 检查全局别名
    if tool_name in GLOBAL_TOOL_ALIASES:
        return GLOBAL_TOOL_ALIASES[tool_name]
    
    # 3. 无别名，返回原名
    return tool_name


def is_alias(tool_name: str) -> bool:
    """
    检查是否是别名
    
    Args:
        tool_name: 工具名
    
    Returns:
        是否是别名
    """
    return tool_name in GLOBAL_TOOL_ALIASES


# 导出
__all__ = [
    "GLOBAL_TOOL_ALIASES",
    "CATEGORY_TOOL_ALIASES",
    "resolve_tool_alias",
    "is_alias",
]
