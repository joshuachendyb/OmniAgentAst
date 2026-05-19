# -*- coding: utf-8 -*-
"""
DESKTOP Schema - 桌面工具 Pydantic 模型

【架构规范】2026-04-29 小沈

【工具列表】统一DESKTOP工具（26→10精简方案）- 小沈 2026-05-17
1. list_windows - 列出所有窗口
2. get_window_info - 获取窗口详细信息
3. window_control - 统一窗口控制（合并set_window_state+focus_window+resize_window）
4. mouse_control - 统一鼠标控制（合并click+move+scroll）
5. keyboard_control - 统一键盘控制（合并type_text+shortcut+key_combo）
6. screen_capture - 统一屏幕截图（合并screenshot+snapshot）
7. clipboard_control - 统一剪贴板控制（合并read_clipboard+write_clipboard）
8. screen_record - 录制屏幕
9. ocr - OCR识别
10. send_notification - 发送通知

【2026-05-19 小沈】参数精简：MouseControlInput 8→6(砍duration+click_type)

创建时间: 2026-04-29
【修正 2026-05-05 小沈】SetWindowStateInput.action 改为 Literal 约束
【2026-05-17 小沈】新增统一入口Schema（WindowControlInput等5个）
"""

from typing import Optional, Literal, Dict, List
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


# ========== 统一入口Schema（26→10精简方案） - 小沈 2026-05-17 ==========

class WindowControlInput(BaseModel):
    """window_control 工具的输入参数 - 统一窗口控制 - 小沈 2026-05-17"""
    window_title: str = Field(
        description="窗口标题（精确匹配或模糊匹配）"
    )
    action: Literal["focus", "resize", "maximize", "minimize", "restore", "topmost", "unpin"] = Field(
        description="窗口操作：focus(聚焦)、resize(调整大小)、maximize(最大化)、minimize(最小化)、restore(还原)、topmost(置顶)、unpin(取消置顶)"
    )
    width: Optional[int] = Field(
        default=None,
        description="窗口宽度（仅resize时使用），单位为像素"
    )
    height: Optional[int] = Field(
        default=None,
        description="窗口高度（仅resize时使用），单位为像素"
    )


class MouseControlInput(BaseModel):
    """mouse_control 工具的输入参数 - 小沈 2026-05-19 参数精简8→6(砍duration+click_type)"""
    action: Literal["click", "move", "scroll", "position"] = Field(
        description="鼠标操作：click(点击)、move(移动)、scroll(滚动)、position(获取位置)"
    )
    x: Optional[int] = Field(
        default=None,
        description="X坐标（click/move时使用）"
    )
    y: Optional[int] = Field(
        default=None,
        description="Y坐标（click/move时使用）"
    )
    button: Optional[Literal["left", "right", "middle"]] = Field(
        default="left",
        description="鼠标按钮（click时使用）：left/right/middle，默认left"
    )
    direction: Optional[Literal["up", "down"]] = Field(
        default="down",
        description="滚动方向（scroll时使用）：up/down，默认down"
    )
    amount: Optional[int] = Field(
        default=3,
        description="滚动单位（scroll时使用），默认3"
    )


class KeyboardControlInput(BaseModel):
    """keyboard_control 工具的输入参数 - 统一键盘控制 - 小沈 2026-05-17"""
    action: Literal["type", "shortcut", "combo"] = Field(
        description="键盘操作：type(输入文本)、shortcut(快捷键)、combo(组合键)"
    )
    text_or_keys: str = Field(
        description="输入内容：type时为文本，shortcut时为快捷键如ctrl+c，combo时为逗号分隔的键如ctrl,shift,esc"
    )
    interval: Optional[float] = Field(
        default=0,
        description="每个字符间隔（type时使用），单位秒，默认0"
    )


class ScreenCaptureInput(BaseModel):
    """screen_capture 工具的输入参数 - 统一屏幕截图 - 小沈 2026-05-17"""
    output_path: Optional[str] = Field(
        default=None,
        description="输出文件路径（可选），不指定则自动生成"
    )
    region: Optional[Dict[str, int]] = Field(
        default=None,
        description="截取区域（可选），如 {\"x\": 0, \"y\": 0, \"width\": 800, \"height\": 600}"
    )
    display: Optional[int] = Field(
        default=None,
        description="显示器编号（可选），主显示器=1，第二显示器=2。指定此参数时使用多显示器快照模式"
    )


class ClipboardControlInput(BaseModel):
    """clipboard_control 工具的输入参数 - 统一剪贴板控制 - 小沈 2026-05-17"""
    action: Literal["read", "write"] = Field(
        description="剪贴板操作：read(读取)、write(写入)"
    )
    content: Optional[str] = Field(
        default=None,
        description="写入内容（仅write时使用）"
    )
