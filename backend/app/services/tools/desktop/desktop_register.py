# -*- coding: utf-8 -*-
"""
DESKTOP Register - 桌面工具注册点

【架构规范】2026-04-29 小沈

【工具列表】窗口管理工具
1. list_windows - 列出所有窗口
2. get_window_info - 获取窗口详细信息
3. set_window_state - 设置窗口状态（最大化/最小化/还原/置顶）

创建时间: 2026-04-29
"""

import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.desktop.desktop_schema import (
    ListWindowsInput,
    GetWindowInfoInput,
    SetWindowStateInput,
)

from app.services.tools.desktop.desktop_tools import (
    list_windows,
    get_window_info,
    set_window_state,
)

# 工具描述
DESKTOP_TOOL_DESCRIPTIONS = {
    "list_windows": "列出当前所有窗口，支持过滤和状态筛选",
    "get_window_info": "获取指定窗口的详细信息（位置、大小、状态等）",
    "set_window_state": "设置窗口状态：最大化、最小化、还原、置顶、取消置顶",
}

# 模型映射
DESKTOP_TOOL_INPUT_MODELS = {
    "list_windows": ListWindowsInput,
    "get_window_info": GetWindowInfoInput,
    "set_window_state": SetWindowStateInput,
}

# 使用示例
DESKTOP_TOOL_EXAMPLES = {
    "list_windows": [
        {},
        {"include_minimized": True},
        {"filter_title": "Chrome"},
    ],
    "get_window_info": [
        {"window_title": "Chrome"},
        {"window_title": "Notepad"},
    ],
    "set_window_state": [
        {"window_title": "Chrome", "action": "maximize"},
        {"window_title": "Notepad", "action": "minimize"},
        {"window_title": "Calculator", "action": "topmost"},
    ],
}


def _register_desktop_tools():
    """
    【2026-04-29 小沈】按文档5.1设计注册所有桌面工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    # 统一的工具映射 - 注册名与实际函数名一致
    tool_methods = {
        "list_windows": list_windows,
        "get_window_info": get_window_info,
        "set_window_state": set_window_state,
    }

    # 注册所有工具
    for name, method in tool_methods.items():
        desc = DESKTOP_TOOL_DESCRIPTIONS.get(name, "")
        input_model = DESKTOP_TOOL_INPUT_MODELS.get(name)
        examples = DESKTOP_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.DESKTOP,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[desktop_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


# 触发注册
_register_desktop_tools()
