# -*- coding: utf-8 -*-
"""
DESKTOP Register - 桌面工具注册点

【2026-06-22 小健】5个窗口状态tool合并为1个set_window_state，16→12

【工具列表】(12个) → DESKTOP分类:
1. window_info - 列出所有窗口 (依赖: pywin32)
2. window_focus - 聚焦窗口 (依赖: pywin32)
3. window_resize - 调整窗口大小 (依赖: pywin32)
4. set_window_state - 窗口状态操作(maximize/minimize/restore/topmost/unpin) (依赖: pywin32)
5. mouse_click - 鼠标单击 (依赖: pyautogui)
6. mouse_move - 移动鼠标 (依赖: pyautogui)
7. mouse_scroll - 鼠标滚轮 (依赖: pyautogui)
8. mouse_position - 获取鼠标位置 (依赖: pyautogui)
9. keyboard_control - 键盘控制 (依赖: pyautogui)
10. screen_capture - 屏幕截图 (依赖: pyautogui)
11. clipboard_read - 读取剪贴板 (依赖: pyperclip)
12. clipboard_write - 写入剪贴板 (依赖: pyperclip)

创建时间: 2026-04-29
更新时间: 2026-06-22 小健
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

DESKTOP_TOOL_DEPENDENCIES = {
    "window_info": [{"import_name": "win32gui", "pip_package": "pywin32"}],
    "window_focus": [{"import_name": "win32gui", "pip_package": "pywin32"}],
    "window_resize": [{"import_name": "win32gui", "pip_package": "pywin32"}],
    "set_window_state": [{"import_name": "win32gui", "pip_package": "pywin32"}],
    "mouse_click": ["pyautogui"],
    "mouse_move": ["pyautogui"],
    "mouse_scroll": ["pyautogui"],
    "mouse_position": ["pyautogui"],
    "keyboard_control": ["pyautogui"],
    "screen_capture": ["mss", "pyautogui"],
    "clipboard_read": ["pyperclip"],
    "clipboard_write": ["pyperclip"],
}

from app.tools.desktop.desktop_schema import (
    WindowInfoInput,
    WindowFocusInput,
    WindowResizeInput,
    SetWindowStateInput,
    MouseClickInput,
    MouseMoveInput,
    MouseScrollInput,
    MousePositionInput,
    KeyboardControlInput,
    ScreenCaptureInput,
    ClipboardReadInput,
    ClipboardWriteInput,
)

from app.tools.desktop.window_info import window_info
from app.tools.desktop.set_window_state import set_window_state
from app.tools.desktop.window_focus import window_focus
from app.tools.desktop.window_resize import window_resize
from app.tools.desktop.mouse_click import mouse_click
from app.tools.desktop.mouse_move import mouse_move
from app.tools.desktop.mouse_scroll import mouse_scroll
from app.tools.desktop.mouse_position import mouse_position
from app.tools.desktop.keyboard_control import keyboard_control
from app.tools.desktop.screen_capture import screen_capture
from app.tools.desktop.clipboard_read import clipboard_read
from app.tools.desktop.clipboard_write import clipboard_write


DESKTOP_TOOL_DESCRIPTIONS = {
    "window_info": """列出当前系统所有可见窗口。可选include_minimized包含最小化窗口,filter_title按标题模糊过滤。返回窗口列表(含标题/状态/位置)。适用场景:需要查看当前打开了哪些窗口、确认窗口名称时使用。""",

    "window_focus": """聚焦(激活)指定窗口,将其置于前台。window_title支持大小写不敏感的模糊匹配。适用场景:需要将特定窗口切换到前台进行操作时使用。""",

    "window_resize": """调整指定窗口的大小。window_title为窗口标题,width/height为目标宽高(像素)。适用场景:需要精确控制窗口尺寸时使用。""",

    "set_window_state": """窗口状态操作。action决定操作类型:maximize(最大化)/minimize(最小化)/restore(还原)/topmost(置顶)/unpin(取消置顶)。window_title支持大小写不敏感的模糊匹配。适用场景:需要控制窗口显示状态时使用。""",

    "mouse_click": """在指定位置进行鼠标单击。x/y为屏幕坐标(可选,不传则在当前位置点击),button为left/right/middle(默认left)。适用场景:需要模拟点击按钮、选择菜单项时使用。""",

    "mouse_move": """移动鼠标到指定屏幕坐标位置。x/y为必填的目标坐标。适用场景:需要将鼠标移动到特定位置进行后续操作时使用。""",

    "mouse_scroll": """模拟鼠标滚轮滚动。direction为up/down(默认down),amount为滚动单位数(默认3)。适用场景:需要滚动页面、浏览长文档时使用。""",

    "mouse_position": """获取鼠标当前的屏幕坐标位置。适用场景:需要确认鼠标当前位置、获取坐标用于后续点击/移动时使用。""",

    "keyboard_control": """键盘控制工具。action=type(输入文本)、shortcut(快捷键如ctrl+c)、combo(组合键如ctrl,shift,esc)。适用场景:需要模拟键盘输入、执行快捷键操作时使用。""",

    "screen_capture": """截取屏幕截图。支持全屏截图、指定区域截图(region参数,格式为{"x":0,"y":0,"width":800,"height":600})和多显示器截图(display参数)。优先使用mss库(支持多显示器),降级使用pyautogui。不指定输出路径则保存到系统临时目录。返回图片保存路径、宽度和高度。适用场景:需要截取当前屏幕内容用于记录或传递给LLM分析时使用。""",

    "clipboard_read": """读取当前系统剪贴板的文本内容。适用场景:需要获取已复制的内容、获取其他程序复制的数据时使用。""",

    "clipboard_write": """将指定文本内容写入系统剪贴板。content参数为必填的写入内容。适用场景:需要将文本复制到剪贴板供其他程序粘贴时使用。""",

}

DESKTOP_TOOL_INPUT_MODELS = {
    "window_info": WindowInfoInput,
    "window_focus": WindowFocusInput,
    "window_resize": WindowResizeInput,
    "set_window_state": SetWindowStateInput,
    "mouse_click": MouseClickInput,
    "mouse_move": MouseMoveInput,
    "mouse_scroll": MouseScrollInput,
    "mouse_position": MousePositionInput,
    "keyboard_control": KeyboardControlInput,
    "screen_capture": ScreenCaptureInput,
    "clipboard_read": ClipboardReadInput,
    "clipboard_write": ClipboardWriteInput,
}

DESKTOP_TOOL_EXAMPLES = {
    "window_info": [
        {},
        {"include_minimized": True},
        {"filter_title": "Chrome"},
    ],
    "window_focus": [
        {"window_title": "Chrome"},
    ],
    "window_resize": [
        {"window_title": "Chrome", "width": 1920, "height": 1080},
    ],
    "set_window_state": [
        {"window_title": "Notepad", "action": "maximize"},
        {"window_title": "Notepad", "action": "minimize"},
        {"window_title": "Notepad", "action": "restore"},
        {"window_title": "Calculator", "action": "topmost"},
        {"window_title": "Calculator", "action": "unpin"},
    ],
    "mouse_click": [
        {"x": 500, "y": 300},
        {"x": 500, "y": 300, "button": "right"},
    ],
    "mouse_move": [
        {"x": 500, "y": 300},
    ],
    "mouse_scroll": [
        {"direction": "down"},
        {"direction": "up", "amount": 5},
    ],
    "mouse_position": [
        {},
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
    "clipboard_read": [
        {},
    ],
    "clipboard_write": [
        {"content": "Hello World"},
    ],
}


def _register_desktop_tools():
    """注册DESKTOP分类工具(12个) — 小健 2026-06-22 5个窗口状态tool合并"""
    tool_methods = {
        "window_info": window_info,
        "window_focus": window_focus,
        "window_resize": window_resize,
        "set_window_state": set_window_state,
        "mouse_click": mouse_click,
        "mouse_move": mouse_move,
        "mouse_scroll": mouse_scroll,
        "mouse_position": mouse_position,
        "keyboard_control": keyboard_control,
        "screen_capture": screen_capture,
        "clipboard_read": clipboard_read,
        "clipboard_write": clipboard_write,
    }

    for name, method in tool_methods.items():
        desc = DESKTOP_TOOL_DESCRIPTIONS.get(name, "")
        input_model = DESKTOP_TOOL_INPUT_MODELS.get(name)
        examples = DESK_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.DESKTOP,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            dependencies=DESKTOP_TOOL_DEPENDENCIES.get(name, []),
        )
        logger.debug(
            f"[desktop_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )

__all__ = ["_register_desktop_tools"]
