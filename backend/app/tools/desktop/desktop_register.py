# -*- coding: utf-8 -*-
"""
DESKTOP Register - 桌面工具注册点

【架构规范】2026-04-29 小沈
【2026-05-17 小沈】26→10精简:统一注册10个LLM可见工具
【2026-06-09 小沈】删除边缘工具:screen_record/ocr/send_notification,10→6
【2026-06-15 小欧】恢复send_notification注册,6→7
【2026-06-17 小欧】组合工具拆分:window_control→7个,mouse_control→4个,clipboard_control→2个,window_info去info
【2026-06-18 小健】添加DESKTOP_TOOL_DEPENDENCIES常量管理工具依赖

【工具列表】(16个) → DESKTOP分类:
1. window_info - 列出所有窗口 (依赖: pygetwindow)
2. window_focus - 聚焦窗口 (依赖: pygetwindow)
3. window_resize - 调整窗口大小 (依赖: pygetwindow)
4. window_maximize - 最大化窗口 (依赖: pygetwindow)
5. window_minimize - 最小化窗口 (依赖: pygetwindow)
6. window_restore - 还原窗口 (依赖: pygetwindow)
7. window_topmost - 窗口置顶 (依赖: pygetwindow)
8. window_unpin - 取消置顶 (依赖: pygetwindow)
9. mouse_click - 鼠标单击 (依赖: pyautogui)
10. mouse_move - 移动鼠标 (依赖: pyautogui)
11. mouse_scroll - 鼠标滚轮 (依赖: pyautogui)
12. mouse_position - 获取鼠标位置 (依赖: pyautogui)
13. keyboard_control - 键盘控制 (依赖: pyautogui)
14. screen_capture - 屏幕截图 (依赖: pyautogui)
15. clipboard_read - 读取剪贴板 (依赖: pyperclip)
16. clipboard_write - 写入剪贴板 (依赖: pyperclip)

【2026-06-18 小健】send_notification移入FUNDAMENTAL分类

创建时间: 2026-04-29
更新时间: 2026-06-18 小健
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

# 桌面工具依赖配置 — 小健 2026-06-18
# 每个工具对应的第三方依赖包列表，支持版本指定
DESKTOP_TOOL_DEPENDENCIES = {
    "window_info": ["pywin32"],
    "window_focus": ["pywin32"],
    "window_resize": ["pywin32"],
    "window_maximize": ["pywin32"],
    "window_minimize": ["pywin32"],
    "window_restore": ["pywin32"],
    "window_topmost": ["pywin32"],
    "window_unpin": ["pywin32"],
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
    WindowMaximizeInput,
    WindowMinimizeInput,
    WindowRestoreInput,
    WindowTopmostInput,
    WindowUnpinInput,
    MouseClickInput,
    MouseMoveInput,
    MouseScrollInput,
    MousePositionInput,
    KeyboardControlInput,
    ScreenCaptureInput,
    ClipboardReadInput,
    ClipboardWriteInput,
)

from app.tools.desktop.desktop_tools import (
    window_info,
    window_focus,
    window_resize,
    window_maximize,
    window_minimize,
    window_restore,
    window_topmost,
    window_unpin,
    mouse_click,
    mouse_move,
    mouse_scroll,
    mouse_position,
    keyboard_control,
    screen_capture,
    clipboard_read,
    clipboard_write,
)


DESKTOP_TOOL_DESCRIPTIONS = {
    "window_info": """列出当前系统所有可见窗口。可选include_minimized包含最小化窗口,filter_title按标题模糊过滤。返回窗口列表(含标题/状态/位置)。适用场景:需要查看当前打开了哪些窗口、确认窗口名称时使用。""",

    "window_focus": """聚焦(激活)指定窗口,将其置于前台。window_title支持大小写不敏感的模糊匹配。适用场景:需要将特定窗口切换到前台进行操作时使用。""",

    "window_resize": """调整指定窗口的大小。window_title为窗口标题,width/height为目标宽高(像素)。适用场景:需要精确控制窗口尺寸时使用。""",

    "window_maximize": """最大化指定窗口。window_title支持大小写不敏感的模糊匹配。适用场景:需要将窗口全屏显示时使用。""",

    "window_minimize": """最小化指定窗口到任务栏。window_title支持大小写不敏感的模糊匹配。适用场景:需要临时隐藏窗口时使用。""",

    "window_restore": """还原窗口到原始大小(从最大化/最小化状态恢复)。window_title支持大小写不敏感的模糊匹配。适用场景:需要恢复已最大化/最小化的窗口时使用。""",

    "window_topmost": """将指定窗口置顶,使其始终显示在其他窗口之上。window_title支持大小写不敏感的模糊匹配。适用场景:需要让窗口始终可见不被遮挡时使用。""",

    "window_unpin": """取消窗口置顶,恢复正常的Z序。window_title支持大小写不敏感的模糊匹配。适用场景:需要取消窗口置顶状态时使用。""",

    "mouse_click": """在指定位置进行鼠标单击。x/y为屏幕坐标(可选,不传则在当前位置点击),button为left/right/middle(默认left)。适用场景:需要模拟点击按钮、选择菜单项时使用。""",

    "mouse_move": """移动鼠标到指定屏幕坐标位置。x/y为必填的目标坐标。适用场景:需要将鼠标移动到特定位置进行后续操作时使用。""",

    "mouse_scroll": """模拟鼠标滚轮滚动。direction为up/down(默认down),amount为滚动单位数(默认3)。适用场景:需要滚动页面、浏览长文档时使用。""",

    "mouse_position": """获取鼠标当前的屏幕坐标位置。适用场景:需要确认鼠标当前位置、获取坐标用于后续点击/移动时使用。""",

    "keyboard_control": """支持键盘控制功能。支持文本输入、快捷键和组合键操作。适用场景:需要模拟键盘输入、执行快捷键操作时使用。""",

    "screen_capture": """截取屏幕截图。支持全屏截图、指定区域截图(region参数,格式为{"x":0,"y":0,"width":800,"height":600})和多显示器截图(display参数)。优先使用mss库(支持多显示器),降级使用pyautogui。不指定输出路径则保存到系统临时目录。返回图片保存路径、宽度和高度。适用场景:需要截取当前屏幕内容用于记录或传递给LLM分析时使用。""",

    "clipboard_read": """读取当前系统剪贴板的文本内容。适用场景:需要获取已复制的内容、获取其他程序复制的数据时使用。""",

    "clipboard_write": """将指定文本内容写入系统剪贴板。content参数为必填的写入内容。适用场景:需要将文本复制到剪贴板供其他程序粘贴时使用。""",

}

DESKTOP_TOOL_INPUT_MODELS = {
    "window_info": WindowInfoInput,
    "window_focus": WindowFocusInput,
    "window_resize": WindowResizeInput,
    "window_maximize": WindowMaximizeInput,
    "window_minimize": WindowMinimizeInput,
    "window_restore": WindowRestoreInput,
    "window_topmost": WindowTopmostInput,
    "window_unpin": WindowUnpinInput,
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
    "window_maximize": [
        {"window_title": "Notepad"},
    ],
    "window_minimize": [
        {"window_title": "Notepad"},
    ],
    "window_restore": [
        {"window_title": "Notepad"},
    ],
    "window_topmost": [
        {"window_title": "Calculator"},
    ],
    "window_unpin": [
        {"window_title": "Calculator"},
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
    """注册DESKTOP分类工具(16个) — 小欧 2026-06-17 拆分组合工具"""
    tool_methods = {
        "window_info": window_info,
        "window_focus": window_focus,
        "window_resize": window_resize,
        "window_maximize": window_maximize,
        "window_minimize": window_minimize,
        "window_restore": window_restore,
        "window_topmost": window_topmost,
        "window_unpin": window_unpin,
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
        examples = DESKTOP_TOOL_EXAMPLES.get(name, [])

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
