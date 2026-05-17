# -*- coding: utf-8 -*-
"""
DESKTOP Register - 桌面工具注册点（26→10精简方案）

【架构规范】2026-04-29 小沈
【2026-05-17 小沈】26→10精简：统一注册10个LLM可见工具

【工具列表】统一DESKTOP工具（10个LLM可见）
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

创建时间: 2026-04-29
更新时间: 2026-05-17
"""

import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.desktop.desktop_schema import (
    ListWindowsInput,
    GetWindowInfoInput,
    WindowControlInput,
    MouseControlInput,
    KeyboardControlInput,
    ScreenCaptureInput,
    ClipboardControlInput,
)

from app.services.tools.desktop.desktop_tools import (
    list_windows,
    get_window_info,
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
    "list_windows": """列出当前所有窗口。

【使用场景】
- 查看所有打开的窗口
- 查找特定窗口
- 筛选窗口列表

【返回数据】
- code: SUCCESS / ERR_LIST_WINDOWS
- data: { windows: [{hwnd, title, state, position}], total }

【示例】
- 所有窗口: {}
- 包含最小化: {"include_minimized": True}
- 过滤标题: {"filter_title": "Chrome"}""",

    "get_window_info": """获取指定窗口的详细信息。

【使用场景】
- 获取窗口属性
- 定位窗口位置
- 查看窗口状态

【返回数据】
- code: SUCCESS / ERR_WINDOW_NOT_FOUND
- data: { hwnd, title, class_name, state, position, process_id, is_visible, is_enabled }

【示例】
- 获取窗口: {"window_title": "Chrome"}""",

    "window_control": """统一窗口控制。合并了 set_window_state + focus_window + resize_window。

【使用场景】
- 聚焦窗口（action="focus"）
- 调整窗口大小（action="resize"，需指定width/height）
- 最大化窗口（action="maximize"）
- 最小化窗口（action="minimize"）
- 还原窗口（action="restore"）
- 置顶窗口（action="topmost"）
- 取消置顶（action="unpin"）

【返回数据】
- code: SUCCESS / ERR_INVALID_ACTION / ERR_WINDOW_NOT_FOUND
- data: { window_title, action, hwnd }

【示例】
- 聚焦: {"window_title": "Chrome", "action": "focus"}
- 最大化: {"window_title": "Notepad", "action": "maximize"}
- 调整大小: {"window_title": "Chrome", "action": "resize", "width": 1920, "height": 1080}
- 置顶: {"window_title": "Calculator", "action": "topmost"}""",

    "mouse_control": """统一鼠标控制。合并了 click + move + scroll + get_mouse_position。

【使用场景】
- 点击（action="click"，可指定x/y/button/click_type）
- 移动（action="move"，需指定x/y，可选duration）
- 滚动（action="scroll"，可指定direction/amount）
- 获取鼠标位置（action="position"）

【重要】需要安装 pyautogui 库

【示例】
- 单击: {"action": "click", "x": 500, "y": 300}
- 双击: {"action": "click", "x": 500, "y": 300, "click_type": "double"}
- 移动: {"action": "move", "x": 500, "y": 300}
- 平滑移动: {"action": "move", "x": 500, "y": 300, "duration": 1.5}
- 滚动: {"action": "scroll", "direction": "down", "amount": 3}
- 获取位置: {"action": "position"}""",

    "keyboard_control": """统一键盘控制。合并了 type_text + shortcut + key_combo。

【使用场景】
- 输入文本（action="type"，text_or_keys为要输入的文本）
- 快捷键（action="shortcut"，text_or_keys为快捷键如ctrl+c）
- 组合键（action="combo"，text_or_keys为逗号分隔的键如ctrl,shift,esc）

【重要】需要安装 pyautogui 库

【示例】
- 输入文本: {"action": "type", "text_or_keys": "Hello World"}
- 模拟打字: {"action": "type", "text_or_keys": "Hello", "interval": 0.1}
- 复制: {"action": "shortcut", "text_or_keys": "ctrl+c"}
- 切换窗口: {"action": "shortcut", "text_or_keys": "alt+tab"}
- 组合键: {"action": "combo", "text_or_keys": "ctrl,shift,esc"}""",

    "screen_capture": """统一屏幕截图。合并了 screenshot + snapshot。

【使用场景】
- 截取全屏（不指定region和display）
- 截取区域（指定region）
- 多显示器快照（指定display，1=主显示器，2=副显示器）

【重要】优先使用mss库（多显示器），降级pyautogui

【示例】
- 截取全屏: {}
- 截取区域: {"region": {"x": 0, "y": 0, "width": 800, "height": 600}}
- 多显示器: {"display": 2}
- 指定路径: {"output_path": "D:/output/screenshot.png"}""",

    "clipboard_control": """统一剪贴板控制。合并了 read_clipboard + write_clipboard。

【使用场景】
- 读取剪贴板（action="read"）
- 写入剪贴板（action="write"，需指定content）

【示例】
- 读取: {"action": "read"}
- 写入: {"action": "write", "content": "Hello World"}""",

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
    "list_windows": ListWindowsInput,
    "get_window_info": GetWindowInfoInput,
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
    "list_windows": [
        {},
        {"include_minimized": True},
        {"filter_title": "Chrome"},
    ],
    "get_window_info": [
        {"window_title": "Chrome"},
    ],
    "window_control": [
        {"window_title": "Chrome", "action": "focus"},
        {"window_title": "Notepad", "action": "maximize"},
        {"window_title": "Chrome", "action": "resize", "width": 1920, "height": 1080},
        {"window_title": "Calculator", "action": "topmost"},
    ],
    "mouse_control": [
        {"action": "click", "x": 500, "y": 300},
        {"action": "click", "x": 500, "y": 300, "click_type": "double"},
        {"action": "move", "x": 500, "y": 300},
        {"action": "move", "x": 500, "y": 300, "duration": 1.5},
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
        "list_windows": list_windows,
        "get_window_info": get_window_info,
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
