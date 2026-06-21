# -*- coding: utf-8 -*-
"""
DESKTOP Schema - 桌面工具参数模型

【Schema Docstring 规范】小健 2026-06-18
一般情况下，严禁给Schema类加docstring。
仅在以下情况可以添加：
1. 函数使用过于复杂，需要详细说明
2. 多action的tool，需要说明不同action的用法
3. 添加的是tool描述的增强信息，不是冗余信息

禁止：
- 重复register.py中的描述
- 添加过于冗长的说明
- 添加与参数无关的内容

创建时间: 2026-04-29
"""

from typing import Optional, Literal, Dict, List
from pydantic import BaseModel, Field


class WindowInfoInput(BaseModel):
    include_minimized: bool = Field(
        default=False,
        description="是否包含最小化的窗口,默认 False"
    )
    filter_title: Optional[str] = Field(
        default=None,
        description="按窗口标题过滤(大小写不敏感的模糊匹配)"
    )


class WindowFocusInput(BaseModel):
    window_title: str = Field(
        description="窗口标题(大小写不敏感的模糊匹配)"
    )


class WindowResizeInput(BaseModel):
    window_title: str = Field(
        description="窗口标题(大小写不敏感的模糊匹配)"
    )
    width: int = Field(
        default=800,
        description="窗口宽度,单位为像素"
    )
    height: int = Field(
        default=600,
        description="窗口高度,单位为像素"
    )


class SetWindowStateInput(BaseModel):
    """窗口状态操作

    【action参数】决定操作类型：
    - maximize: 最大化窗口
    - minimize: 最小化窗口
    - restore: 还原窗口
    - topmost: 窗口置顶
    - unpin: 取消置顶
    """
    window_title: str = Field(
        description="窗口标题(大小写不敏感的模糊匹配)"
    )
    action: Literal["maximize", "minimize", "restore", "topmost", "unpin"] = Field(
        description="窗口操作:maximize(最大化)/minimize(最小化)/restore(还原)/topmost(置顶)/unpin(取消置顶)"
    )


class MouseClickInput(BaseModel):
    x: Optional[int] = Field(
        default=None,
        description="X坐标,不传则在当前鼠标位置点击"
    )
    y: Optional[int] = Field(
        default=None,
        description="Y坐标,不传则在当前鼠标位置点击"
    )
    button: Literal["left", "right", "middle"] = Field(
        default="left",
        description="鼠标按钮:left/right/middle,默认left"
    )


class MouseMoveInput(BaseModel):
    x: int = Field(
        description="目标X坐标"
    )
    y: int = Field(
        description="目标Y坐标"
    )


class MouseScrollInput(BaseModel):
    direction: Literal["up", "down"] = Field(
        default="down",
        description="滚动方向:up/down,默认down"
    )
    amount: int = Field(
        default=3,
        description="滚动单位,默认3"
    )


class MousePositionInput(BaseModel):
    pass


class KeyboardControlInput(BaseModel):
    """键盘控制工具
    
    【action参数】决定操作类型：
    - type: 输入文本
    - shortcut: 执行快捷键
    - combo: 执行组合键
    
    【使用示例】
    - 输入文本 → keyboard_control(action="type", text_or_keys="Hello World")
    - 快捷键 → keyboard_control(action="shortcut", text_or_keys="ctrl+c")
    - 组合键 → keyboard_control(action="combo", text_or_keys="ctrl,shift,esc")
    """
    action: Literal["type", "shortcut", "combo"] = Field(
        description="键盘操作:type(输入文本)、shortcut(快捷键)、combo(组合键)"
    )
    text_or_keys: str = Field(
        description="输入内容:type时为文本,shortcut时为快捷键如ctrl+c,combo时为逗号分隔的键如ctrl,shift,esc"
    )
    interval: float = Field(
        default=0,
        description="每个字符间隔(type时使用),单位秒,默认0。注意:仅对ASCII字符有效,非ASCII字符使用write()不支持间隔"
    )


class ScreenCaptureInput(BaseModel):
    output_path: Optional[str] = Field(
        default=None,
        description="输出文件路径(可选)。不传则保存到系统临时目录如<temp>/screenshot_<时间戳>.png"
    )
    region: Optional[Dict[str, int]] = Field(
        default=None,
        description="截取区域(可选)。Dict键:x(默认0)/y(默认0)/width(默认800)/height(默认600)"
    )
    display: Optional[int] = Field(
        default=None,
        description="显示器编号(可选),1=主显示器,2=第二显示器。指定display时,region和output_path参数将被忽略"
    )


class ClipboardReadInput(BaseModel):
    pass


class ClipboardWriteInput(BaseModel):
    content: str = Field(
        description="要写入剪贴板的内容"
    )


__all__ = [
    "WindowInfoInput",
    "WindowFocusInput",
    "WindowResizeInput",
    "SetWindowStateInput",
    "MouseClickInput",
    "MouseMoveInput",
    "MouseScrollInput",
    "MousePositionInput",
    "KeyboardControlInput",
    "ScreenCaptureInput",
    "ClipboardReadInput",
    "ClipboardWriteInput",
]
