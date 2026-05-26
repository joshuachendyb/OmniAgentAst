# -*- coding: utf-8 -*-
"""
DESKTOP Schema - 桌面工具 Pydantic 模型

【架构规范】2026-04-29 小沈

【工具列表】统一DESKTOP工具（10→9精简，Ch19）- 小沈 2026-05-22
1. window_info - 窗口信息查询（合并list_windows+get_window_info）
2. window_control - 统一窗口控制（合并set_window_state+focus_window+resize_window）
3. mouse_control - 统一鼠标控制（合并click+move+scroll）
4. keyboard_control - 统一键盘控制（合并type_text+shortcut+key_combo）
5. screen_capture - 统一屏幕截图（合并screenshot+snapshot）
6. clipboard_control - 统一剪贴板控制（合并read_clipboard+write_clipboard）
7. screen_record - 录制屏幕
8. ocr - OCR识别
9. send_notification - 发送通知

【2026-05-19 小沈】参数精简：MouseControlInput 8→6(砍duration+click_type)

创建时间: 2026-04-29
【修正 2026-05-05 小沈】SetWindowStateInput.action 改为 Literal 约束
【2026-05-17 小沈】新增统一入口Schema（WindowControlInput等5个）
"""

from typing import Optional, Literal, Dict, List
from pydantic import BaseModel, Field


class WindowInfoInput(BaseModel):
    """window_info 工具的输入参数 - 窗口信息查询 - 小沈 2026-05-22"""
    action: Literal["list", "info"] = Field(
        description="查询操作：list(列出所有窗口)、info(获取单个窗口详细信息)"
    )
    window_title: Optional[str] = Field(
        default=None,
        description="窗口标题（action=info时必填，大小写不敏感的模糊匹配）"
    )
    include_minimized: bool = Field(
        default=False,
        description="是否包含最小化的窗口（action=list时使用），默认 False"
    )
    filter_title: Optional[str] = Field(
        default=None,
        description="按窗口标题过滤（action=list时使用，大小写不敏感的模糊匹配）"
    )


# ========== 统一入口Schema（26→10精简方案） - 小沈 2026-05-17 ==========

class WindowControlInput(BaseModel):
    """window_control 工具的输入参数 - 统一窗口控制 - 小沈 2026-05-17"""
    window_title: str = Field(
        description="窗口标题（大小写不敏感的模糊匹配）"
    )
    action: Literal["focus", "resize", "maximize", "minimize", "restore", "topmost", "unpin"] = Field(
        description="窗口操作：focus(聚焦)、resize(调整大小)、maximize(最大化)、minimize(最小化)、restore(还原)、topmost(置顶)、unpin(取消置顶)"
    )
    width: Optional[int] = Field(
        default=None,
        description="窗口宽度（仅resize时使用），单位为像素。不传则保持原宽度"
    )
    height: Optional[int] = Field(
        default=None,
        description="窗口高度（仅resize时使用），单位为像素。不传则保持原高度"
    )


class MouseControlInput(BaseModel):
    """mouse_control 工具的输入参数 - 小沈 2026-05-19 参数精简8→6(砍duration+click_type)"""
    action: Literal["click", "move", "scroll", "position"] = Field(
        description="鼠标操作：click(单击)、move(移动)、scroll(滚动)、position(获取位置)。注意：click仅支持单击"
    )
    x: Optional[int] = Field(
        default=None,
        description="X坐标（click/move时使用）。click不传则在当前鼠标位置点击"
    )
    y: Optional[int] = Field(
        default=None,
        description="Y坐标（click/move时使用）。click不传则在当前鼠标位置点击"
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
    interval: float = Field(
        default=0,
        description="每个字符间隔（type时使用），单位秒，默认0。注意：仅对ASCII字符有效，非ASCII字符使用write()不支持间隔"
    )


class ScreenCaptureInput(BaseModel):
    """screen_capture 工具的输入参数 - 统一屏幕截图 - 小沈 2026-05-17"""
    output_path: Optional[str] = Field(
        default=None,
        description="输出文件路径（可选）。不传则保存到系统临时目录如<temp>/screenshot_<时间戳>.png"
    )
    region: Optional[Dict[str, int]] = Field(
        default=None,
        description="截取区域（可选）。Dict键：x(默认0)/y(默认0)/width(默认800)/height(默认600)"
    )
    display: Optional[int] = Field(
        default=None,
        description="显示器编号（可选），1=主显示器，2=第二显示器。指定display时，region和output_path参数将被忽略"
    )


class ClipboardControlInput(BaseModel):
    """clipboard_control 工具的输入参数 - 统一剪贴板控制 - 小沈 2026-05-17"""
    action: Literal["read", "write"] = Field(
        description="剪贴板操作：read(读取)、write(写入)"
    )
    content: Optional[str] = Field(
        default=None,
        description="写入内容（action=write时必填，不传则返回ERR_MISSING_PARAM）"
    )
