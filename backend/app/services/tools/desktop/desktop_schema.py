# -*- coding: utf-8 -*-
"""
DESKTOP Schema - 桌面工具 Pydantic 模型

创建时间: 2026-04-29
"""

from typing import Optional, Literal, Dict, List
from pydantic import BaseModel, Field


class WindowInfoInput(BaseModel):
    action: Literal["list", "info"] = Field(
        description="查询操作:list(列出所有窗口)、info(获取单个窗口详细信息)"
    )
    window_title: Optional[str] = Field(
        default=None,
        description="窗口标题(action=info时【必填】,大小写不敏感的模糊匹配)"
    )
    include_minimized: bool = Field(
        default=False,
        description="是否包含最小化的窗口(仅action=list时使用),默认 False"
    )
    filter_title: Optional[str] = Field(
        default=None,
        description="按窗口标题过滤(仅action=list时使用,大小写不敏感的模糊匹配)"
    )


class WindowControlInput(BaseModel):
    window_title: str = Field(
        description="窗口标题(大小写不敏感的模糊匹配)"
    )
    action: Literal["focus", "resize", "maximize", "minimize", "restore", "topmost", "unpin"] = Field(
        description="窗口操作:focus(聚焦)、resize(调整大小)、maximize(最大化)、minimize(最小化)、restore(还原)、topmost(置顶)、unpin(取消置顶)"
    )
    width: Optional[int] = Field(
        default=None,
        description="窗口宽度(仅resize时使用),单位为像素。不传则保持原宽度"
    )
    height: Optional[int] = Field(
        default=None,
        description="窗口高度(仅resize时使用),单位为像素。不传则保持原高度"
    )


class MouseControlInput(BaseModel):
    action: Literal["click", "move", "scroll", "position"] = Field(
        description="鼠标操作:click(单击)、move(移动)、scroll(滚动)、position(获取位置)。注意:click仅支持单击"
    )
    x: Optional[int] = Field(
        default=None,
        description="X坐标(click/move时使用)。click不传则在当前鼠标位置点击"
    )
    y: Optional[int] = Field(
        default=None,
        description="Y坐标(click/move时使用)。click不传则在当前鼠标位置点击"
    )
    button: Optional[Literal["left", "right", "middle"]] = Field(
        default="left",
        description="鼠标按钮(click时使用):left/right/middle,默认left"
    )
    direction: Optional[Literal["up", "down"]] = Field(
        default="down",
        description="滚动方向(scroll时使用):up/down,默认down"
    )
    amount: Optional[int] = Field(
        default=3,
        description="滚动单位(scroll时使用),默认3"
    )


class KeyboardControlInput(BaseModel):
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


class ClipboardControlInput(BaseModel):
    action: Literal["read", "write"] = Field(
        description="剪贴板操作:read(读取)、write(写入)"
    )
    content: Optional[str] = Field(
        default=None,
        description="写入内容(action=write时【必填】)"
    )


class SendNotificationInput(BaseModel):
    title: str = Field(
        description="通知标题,例如:'AI热点新闻'"
    )
    message: str = Field(
        description="通知正文,例如:'已为您搜索到最新AI行业新闻'"
    )
    duration: int = Field(
        default=5,
        description="通知显示时长(秒),默认5秒"
    )
