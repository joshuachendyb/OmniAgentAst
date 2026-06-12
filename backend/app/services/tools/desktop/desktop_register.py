# -*- coding: utf-8 -*-
"""
DESKTOP Register - 桌面工具注册点

【架构规范】2026-04-29 小沈
【2026-05-17 小沈】26→10精简:统一注册10个LLM可见工具
【2026-06-09 小沈】删除边缘工具:screen_record/ocr/send_notification,10→6

【工具列表】统一SCREEN分类工具(6个)
1. window_info - 窗口信息查询(合并list_windows+get_window_info)
2. window_control - 统一窗口控制(合并set_window_state+focus_window+resize_window)
3. mouse_control - 统一鼠标控制(合并click+move+scroll)
4. keyboard_control - 统一键盘控制(合并type_text+shortcut+key_combo)
5. screen_capture - 统一屏幕截图(合并screenshot+snapshot)
6. clipboard_control - 统一剪贴板控制(合并read_clipboard+write_clipboard)

创建时间: 2026-04-29
更新时间: 2026-06-09
"""

import logging
from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger

from app.services.tools.desktop.desktop_schema import (
    WindowInfoInput,
    WindowControlInput,
    MouseControlInput,
    KeyboardControlInput,
    ScreenCaptureInput,
    ClipboardControlInput,
)

from app.services.tools.desktop.desktop_tools import (
    window_info,
    window_control,
    mouse_control,
    keyboard_control,
    screen_capture,
    clipboard_control,
)


DESKTOP_TOOL_DESCRIPTIONS = {
    "window_info": """支持窗口信息查询功能。
action参数决定操作类型:
- list: 列出所有窗口(可选include_minimized/filter_title)
- info: 获取单个窗口详细信息,window_title

使用示例:
- 列出窗口 → window_info(action="list")
- 窗口详情 → window_info(action="info", window_title="Chrome")""",

    "window_control": """支持窗口控制功能。
action参数决定操作类型:
- focus: 聚焦窗口,window_title
- maximize: 最大化窗口,window_title
- minimize: 最小化窗口,window_title
- restore: 还原窗口,window_title
- resize: 调整窗口大小,window_title(可选width/height)
- topmost: 窗口置顶,window_title
- unpin: 取消置顶,window_title

使用示例:
- 聚焦 → window_control(action="focus", window_title="Chrome")
- 最大化 → window_control(action="maximize", window_title="Notepad")
- 调整大小 → window_control(action="resize", window_title="Chrome", width=1920, height=1080)
- 置顶 → window_control(action="topmost", window_title="Calculator")""",

    "mouse_control": """支持鼠标控制功能。
action参数决定操作类型:
- click: 单击,可选x/y/button(不传坐标则在当前位置点击)
- move: 移动鼠标,x+y
- scroll: 滚动,可选direction/amount
- position: 获取鼠标当前位置

使用示例:
- 单击 → mouse_control(action="click", x=500, y=300)
- 移动 → mouse_control(action="move", x=500, y=300)
- 滚动 → mouse_control(action="scroll", direction="down", amount=3)
- 获取位置 → mouse_control(action="position")""",

    "keyboard_control": """支持键盘控制功能。
action参数决定操作类型:
- type: 输入文本,text_or_keys(可选interval)
- shortcut: 快捷键,text_or_keys(如ctrl+c)
- combo: 组合键,text_or_keys(逗号分隔如ctrl,shift,esc)

使用示例:
- 输入文本 → keyboard_control(action="type", text_or_keys="Hello World")
- 快捷键 → keyboard_control(action="shortcut", text_or_keys="ctrl+c")
- 组合键 → keyboard_control(action="combo", text_or_keys="ctrl,shift,esc")""",

    "screen_capture": """统一屏幕截图 - 合并screenshot + snapshot功能。

【使用场景】
- 截取全屏 / 截取区域 / 多显示器快照

【重要】优先使用mss库(多显示器),降级pyautogui

【使用示例】【常用名转换说明】
- 截取全屏/screenshot → screen_capture()
- 截取区域/snapshot → screen_capture(region={"x":0,"y":0,"width":800,"height":600})
- 多显示器 → screen_capture(display=2)
- 指定路径 → screen_capture(output_path="D:/output/screenshot.png")

【返回数据说明】
- data.success/data.image_path/data.width/data.height""",

    "clipboard_control": """支持剪贴板的读/写操作功能。
action参数决定操作类型:
- read: 读取剪贴板内容
- write: 写入剪贴板,content

使用示例:
- 读取 → clipboard_control(action="read")
- 写入 → clipboard_control(action="write", content="Hello World")""",
}

DESKTOP_TOOL_INPUT_MODELS = {
    "window_info": WindowInfoInput,
    "window_control": WindowControlInput,
    "mouse_control": MouseControlInput,
    "keyboard_control": KeyboardControlInput,
    "screen_capture": ScreenCaptureInput,
    "clipboard_control": ClipboardControlInput,

}

DESKTOP_TOOL_EXAMPLES = {
    "window_info": [
        {"action": "list"},
        {"action": "list", "include_minimized": True},
        {"action": "list", "filter_title": "Chrome"},
        {"action": "info", "window_title": "Chrome"},
    ],
    "window_control": [
        {"window_title": "Chrome", "action": "focus"},
        {"window_title": "Notepad", "action": "maximize"},
        {"window_title": "Chrome", "action": "resize", "width": 1920, "height": 1080},
        {"window_title": "Calculator", "action": "topmost"},
    ],
    "mouse_control": [
        {"action": "click", "x": 500, "y": 300},
        {"action": "click", "x": 500, "y": 300, "button": "right"},
        {"action": "move", "x": 500, "y": 300},
        {"action": "scroll", "direction": "down"},
        {"action": "position"},
    ],
    "keyboard_control": [
        {"action": "type", "text_or_keys": "Hello World"},
        {"action": "type", "text_or_keys": "Hello", "interval": 0.1},
        {"action": "shortcut", "text_or_keys": "ctrl+c"},
        {"action": "shortcut", "text_or_keys": "alt+tab"},
        {"action": "combo", "text_or_keys": "ctrl,shift,esc"},
    ],
    "screen_capture": [
        {},
        {"region": {"x": 0, "y": 0, "width": 800, "height": 600}},
        {"display": 2},
    ],
    "clipboard_control": [
        {"action": "read"},
        {"action": "write", "content": "Hello World"},
    ],

}


def _register_desktop_tools():
    """注册SCREEN分类工具(6个) — 小沈 2026-06-09 删除边缘工具"""
    tool_methods = {
        "window_info": window_info,
        "window_control": window_control,
        "mouse_control": mouse_control,
        "keyboard_control": keyboard_control,
        "screen_capture": screen_capture,
        "clipboard_control": clipboard_control,
    }

    for name, method in tool_methods.items():
        desc = DESKTOP_TOOL_DESCRIPTIONS.get(name, "")
        input_model = DESKTOP_TOOL_INPUT_MODELS.get(name)
        examples = DESKTOP_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.SCREEN,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.debug(
            f"[desktop_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )

__all__ = ["_register_desktop_tools"]
