# -*- coding: utf-8 -*-
"""
DESKTOP Register - 桌面工具注册点（26→10精简方案）

【架构规范】2026-04-29 小沈
【2026-05-17 小沈】26→10精简：统一注册10个LLM可见工具

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

创建时间: 2026-04-29
更新时间: 2026-05-17
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

from app.services.tools.desktop.gui_tools import (
    screen_record,
    ocr,
    send_notification,
)

from app.services.tools.desktop.gui_schema import (
    ScreenRecordInput,
    OcrInput,
    SendNotificationInput,
)

DESKTOP_TOOL_DESCRIPTIONS = {
    "window_info": """统一窗口信息查询 - 合并list_windows + get_window_info功能。

【使用场景】
- 列出所有窗口（action="list"，可选 include_minimized/filter_title 筛选）
- 获取单个窗口的详细信息（action="info"，需指定 window_title）

【使用示例】【常用名转换说明】
- 列出窗口/list_windows → window_info(action="list")
- 含最小化 → window_info(action="list", include_minimized=true)
- 过滤窗口 → window_info(action="list", filter_title="Chrome")
- 窗口详情/get_window_info → window_info(action="info", window_title="Chrome")

【返回数据说明】
- list: data.windows(窗口列表)/data.total
- info: data.hwnd/data.title/data.class_name/data.state/data.position/data.process_id""",

    "window_control": """统一窗口控制 - 合并set_window_state + focus_window + resize_window功能。

【使用场景】
- 聚焦/最大化/最小化/还原/置顶/取消置顶/调整大小

【使用示例】【常用名转换说明】
- 聚焦/focus_window → window_control(action="focus", window_title="Chrome")
- 最大化/set_window_state → window_control(action="maximize", window_title="Notepad")
- 最小化 → window_control(action="minimize", window_title="Notepad")
- 还原 → window_control(action="restore", window_title="Notepad")
- 调整大小/resize_window → window_control(action="resize", window_title="Chrome", width=1920, height=1080)
- 置顶 → window_control(action="topmost", window_title="Calculator")
- 取消置顶 → window_control(action="unpin", window_title="Calculator")

【返回数据说明】
- data.window_title/data.action/data.hwnd""",

    "mouse_control": """统一鼠标控制 - 合并click + move + scroll + get_mouse_position功能。

【使用场景】
- 点击（action="click"）/ 移动（action="move"）/ 滚动（action="scroll"）/ 获取位置（action="position"）

【重要】需要安装 pyautogui 库

【使用示例】【常用名转换说明】
- 单击/click → mouse_control(action="click", x=500, y=300)
- 右击 → mouse_control(action="click", x=500, y=300, button="right")
- 移动/move → mouse_control(action="move", x=500, y=300)
- 滚动/scroll → mouse_control(action="scroll", direction="down", amount=3)
- 获取位置/get_mouse_position → mouse_control(action="position")

【返回数据说明】
- data.success/data.action/data.position""",

    "keyboard_control": """统一键盘控制 - 合并type_text + shortcut + key_combo功能。

【使用场景】
- 输入文本（action="type"）/ 快捷键（action="shortcut"）/ 组合键（action="combo"）

【重要】需要安装 pyautogui 库

【使用示例】【常用名转换说明】
- 输入文本/type_text → keyboard_control(action="type", text_or_keys="Hello World")
- 模拟打字 → keyboard_control(action="type", text_or_keys="Hello", interval=0.1)
- 快捷键/shortcut → keyboard_control(action="shortcut", text_or_keys="ctrl+c")
- 组合键/key_combo → keyboard_control(action="combo", text_or_keys="ctrl,shift,esc")

【返回数据说明】
- data.success/data.action""",

    "screen_capture": """统一屏幕截图 - 合并screenshot + snapshot功能。

【使用场景】
- 截取全屏 / 截取区域 / 多显示器快照

【重要】优先使用mss库（多显示器），降级pyautogui

【使用示例】【常用名转换说明】
- 截取全屏/screenshot → screen_capture()
- 截取区域/snapshot → screen_capture(region={"x":0,"y":0,"width":800,"height":600})
- 多显示器 → screen_capture(display=2)
- 指定路径 → screen_capture(output_path="D:/output/screenshot.png")

【返回数据说明】
- data.success/data.image_path/data.width/data.height""",

    "clipboard_control": """统一剪贴板控制 - 合并read_clipboard + write_clipboard功能。

【使用场景】
- 读取剪贴板（action="read"）/ 写入剪贴板（action="write"）

【使用示例】【常用名转换说明】
- 读取/read_clipboard → clipboard_control(action="read")
- 写入/write_clipboard → clipboard_control(action="write", content="Hello World")

【返回数据说明】
- read: data.content
- write: data.success""",

    "screen_record": """录制屏幕视频。

【使用场景】
- 录制屏幕操作过程
- 制作操作教程或演示视频

【重要】需要安装 mss + PIL + numpy + imageio 库

【示例】
- 录制30秒: {"duration": 30}
- 高清录制: {"duration": 60, "output_path": "D:/output/demo.mp4", "fps": 30}""",

    "ocr": """从图片中识别文字（OCR）。

【使用场景】
- 从图片中提取文字内容
- 识别截图中的文字

【重要】需要安装 pytesseract 库和 Tesseract OCR 引擎

【示例】
- 英文识别: {"image_path": "D:/images/screenshot.png"}
- 中文识别: {"image_path": "D:/images/screenshot.png", "language": "chi_sim"}""",

    "send_notification": """发送 Windows 系统通知。

【使用场景】
- 发送系统通知提醒
- 通知用户操作完成

【重要】需要安装 win10toast 库

【示例】
- 发送通知: {"title": "任务完成", "message": "数据处理已完成"}
- 自定义时长: {"title": "提醒", "message": "请检查结果", "duration": 10}""",
}

DESKTOP_TOOL_INPUT_MODELS = {
    "window_info": WindowInfoInput,
    "window_control": WindowControlInput,
    "mouse_control": MouseControlInput,
    "keyboard_control": KeyboardControlInput,
    "screen_capture": ScreenCaptureInput,
    "clipboard_control": ClipboardControlInput,
    "screen_record": ScreenRecordInput,
    "ocr": OcrInput,
    "send_notification": SendNotificationInput,
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
    "screen_record": [
        {"duration": 30},
        {"duration": 60, "output_path": "D:/output/demo.mp4", "fps": 30},
    ],
    "ocr": [
        {"image_path": "D:/images/screenshot.png"},
        {"image_path": "D:/images/screenshot.png", "language": "chi_sim"},
    ],
    "send_notification": [
        {"title": "任务完成", "message": "文件已成功保存"},
        {"title": "提醒", "message": "请检查结果", "duration": 10},
    ],
}


def _register_desktop_tools():
    """
    【2026-05-17 小沈】26→10精简方案：注册统一DESKTOP分类的10个LLM可见工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "window_info": window_info,
        "window_control": window_control,
        "mouse_control": mouse_control,
        "keyboard_control": keyboard_control,
        "screen_capture": screen_capture,
        "clipboard_control": clipboard_control,
        "screen_record": screen_record,
        "ocr": ocr,
        "send_notification": send_notification,
    }

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


_initialized = False

__all__ = ["_register_desktop_tools"]
