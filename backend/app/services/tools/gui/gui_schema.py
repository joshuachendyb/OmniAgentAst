# -*- coding: utf-8 -*-
"""
GUI 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按文档第9章 Tool 92-104 定义

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ClickInput(BaseModel):
    """click 工具的输入参数（Tool 92）"""
    x: Optional[int] = Field(default=None, description="点击的 X 坐标（可选）。屏幕水平位置，从左上角开始计算")
    y: Optional[int] = Field(default=None, description="点击的 Y 坐标（可选）。屏幕垂直位置，从左上角开始计算")
    button: Optional[str] = Field(default="left", description="鼠标按钮（可选）。Agent根据query推断，右键菜单→right，中键→middle")
    click_type: Optional[str] = Field(default="single", description="点击类型（可选）。Agent根据query推断，\"双击\"→double")


class MoveInput(BaseModel):
    """move 工具的输入参数（Tool 93）"""
    x: int = Field(..., description="目标 X 坐标。屏幕水平位置，从左上角开始计算")
    y: int = Field(..., description="目标 Y 坐标。屏幕垂直位置，从左上角开始计算")
    duration: Optional[float] = Field(default=0, description="移动持续时间（可选），单位为秒")


class ScrollInput(BaseModel):
    """scroll 工具的输入参数（Tool 94）"""
    direction: str = Field(..., description="滚动方向。可选值：up（向上滚动）、down（向下滚动）")
    amount: Optional[int] = Field(default=3, description="滚动单位数量（可选）")


class TypeTextInput(BaseModel):
    """type_text 工具的输入参数（Tool 95）"""
    text: str = Field(..., description="要输入的文本。支持中英文输入")
    interval: Optional[float] = Field(default=0, description="每个字符间隔（可选），单位为秒")


class ShortcutInput(BaseModel):
    """shortcut 工具的输入参数（Tool 96）"""
    keys: str = Field(..., description="快捷键组合。如 ctrl+c, alt+tab")


class KeyComboInput(BaseModel):
    """key_combo 工具的输入参数（Tool 97）"""
    keys: List[str] = Field(..., description="要按住的键数组。如 [\"ctrl\", \"shift\", \"esc\"]")
    action: Optional[str] = Field(default="press", description="操作（可选）。可选值：press/hold/release")


class ScreenshotInput(BaseModel):
    """screenshot 工具的输入参数（Tool 98）"""
    output_path: Optional[str] = Field(default=None, description="输出文件路径（可选）。Agent根据上下文自动生成，含时间戳")
    region: Optional[Dict[str, int]] = Field(default=None, description="截取区域（可选）。如 {\"x\": 0, \"y\": 0, \"width\": 800, \"height\": 600}")


class SnapshotInput(BaseModel):
    """snapshot 工具的输入参数（Tool 99）"""
    display: Optional[int] = Field(default=1, description="显示器编号（可选）。主显示器→1，第二显示器→2")


class ScreenRecordInput(BaseModel):
    """screen_record 工具的输入参数（Tool 100）"""
    duration: int = Field(..., description="录制时长，单位为秒")
    output_path: Optional[str] = Field(default=None, description="输出文件路径（可选）")
    fps: Optional[int] = Field(default=15, description="帧率（可选）")


class FocusWindowInput(BaseModel):
    """focus_window 工具的输入参数（Tool 103）"""
    title: str = Field(..., description="窗口标题。如 \"Chrome\" 或 \"记事本\"，会模糊匹配")


class ResizeWindowInput(BaseModel):
    """resize_window 工具的输入参数（Tool 104）"""
    title: str = Field(..., description="窗口标题。如 \"Chrome\" 或 \"记事本\"，会模糊匹配")
    width: Optional[int] = Field(default=None, description="宽度（可选）。窗口的新宽度，单位为像素")
    height: Optional[int] = Field(default=None, description="高度（可选）。窗口的新高度，单位为像素")


class OcrInput(BaseModel):
    """ocr 工具的输入参数（Tool 101）"""
    image_path: str = Field(..., description="图片文件路径。如 D:/images/screenshot.png")
    language: Optional[str] = Field(default="eng", description="识别语言（可选）。可选值：eng/chi_sim/eng+chi_sim")


class ListWindowsInput(BaseModel):
    """list_windows 工具的输入参数（Tool 102）"""
    filter: Optional[str] = Field(default=None, description="窗口标题过滤（可选）。如 \"Chrome\" 只返回标题包含 Chrome 的窗口")


class ReadClipboardInput(BaseModel):
    """read_clipboard 工具的输入参数（Tool 105）- 按文档9.6节定义"""
    pass


class WriteClipboardInput(BaseModel):
    """write_clipboard 工具的输入参数（Tool 106）- 按文档9.6节定义"""
    content: str = Field(..., description="要写入的内容。任意文本内容")


class SendNotificationInput(BaseModel):
    """send_notification 工具的输入参数（Tool 107）- 按文档9.7节定义"""
    title: str = Field(..., description="通知标题。如 \"任务完成\"、\"提醒\"")
    message: str = Field(..., description="通知内容。通知的详细信息")
    duration: Optional[int] = Field(default=5, description="显示时长（可选），单位为秒。默认5秒")


__all__ = [
    "ClickInput",
    "MoveInput",
    "ScrollInput",
    "TypeTextInput",
    "ShortcutInput",
    "KeyComboInput",
    "ScreenshotInput",
    "SnapshotInput",
    "ScreenRecordInput",
    "FocusWindowInput",
    "ResizeWindowInput",
    "OcrInput",
    "ListWindowsInput",
    "ReadClipboardInput",
    "WriteClipboardInput",
    "SendNotificationInput",
]
