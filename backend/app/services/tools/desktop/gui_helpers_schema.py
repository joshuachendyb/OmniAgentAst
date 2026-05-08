# -*- coding: utf-8 -*-
"""
GUI 辅助工具 Schema 定义

【架构规范】2026-05-04 小沈

创建时间: 2026-05-04
更新时间: 2026-05-04
"""

from pydantic import BaseModel


class GetMousePositionInput(BaseModel):
    """获取鼠标位置输入模型（Tool 108）"""
    pass


class CheckScreenSizeInput(BaseModel):
    """检查屏幕分辨率输入模型（Tool 109）"""
    pass


class CheckWindowExistsInput(BaseModel):
    """检查窗口是否存在输入模型（Tool 110）

    属性：
        title: 窗口标题（模糊匹配）
    """
    title: str


class GetWindowPositionInput(BaseModel):
    """获取窗口位置和大小输入模型（Tool 111）

    属性：
        title: 窗口标题（模糊匹配）
    """
    title: str


class CheckScreenCapturePermissionInput(BaseModel):
    """检查屏幕捕获权限输入模型（Tool 112）"""
    pass


class CheckTesseractAvailableInput(BaseModel):
    """检查 Tesseract 可用性输入模型（Tool 113）"""
    pass


class CheckNotificationPermissionInput(BaseModel):
    """检查通知权限输入模型（Tool 114）"""
    pass