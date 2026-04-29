# -*- coding: utf-8 -*-
"""
DESKTOP Schema - 桌面工具 Pydantic 模型

【架构规范】2026-04-29 小沈

【工具列表】窗口管理工具
1. list_windows - 列出所有窗口
2. get_window_info - 获取窗口详细信息
3. set_window_state - 设置窗口状态（最大化/最小化/还原/置顶）

创建时间: 2026-04-29
"""

from typing import Optional
from pydantic import BaseModel, Field


class ListWindowsInput(BaseModel):
    """list_windows 工具的输入参数 - 列出所有窗口"""
    include_minimized: bool = Field(
        default=False,
        description="是否包含最小化的窗口，默认 False"
    )
    filter_title: Optional[str] = Field(
        default=None,
        description="按窗口标题过滤（支持模糊匹配）"
    )


class GetWindowInfoInput(BaseModel):
    """get_window_info 工具的输入参数 - 获取窗口详细信息"""
    window_title: str = Field(
        description="窗口标题（精确匹配或模糊匹配）"
    )


class SetWindowStateInput(BaseModel):
    """set_window_state 工具的输入参数 - 设置窗口状态"""
    window_title: str = Field(
        description="窗口标题（精确匹配或模糊匹配）"
    )
    action: str = Field(
        description="窗口操作：maximize(最大化)、minimize(最小化)、restore(还原)、topmost(置顶)、unpin(取消置顶)"
    )
