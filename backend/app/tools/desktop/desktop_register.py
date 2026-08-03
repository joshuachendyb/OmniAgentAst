# -*- coding: utf-8 -*-
"""
DESKTOP Register - 桌面工具注册点

【2026-06-22 小健】5个窗口状态tool合并为1个set_window_state，16→12
【2026-07-20 小欧】加描述规范:工具描述保持简洁不冗余,能力详情与默认支持能力只写在 schema 类 docstring,禁止在 register 工具描述里重复

【工具列表】(11个) → DESKTOP分类:
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
11. clipboard_control - 剪贴板操作(read/write) (依赖: pyperclip)

创建时间: 2026-04-29
更新时间: 2026-07-30 小欧 — 整改:#2 amount,#3坐标,#4子串匹配,#5传0保持原大小
# 2026-07-30 - 小欧 - #8补window_info默认值; #9/#13 mouse_click补"绝对"; #11补display:1示例; #12补width=0示例
# 2026-07-30 - 小欧 - #12:screen_capture描述补充display/region/dest互斥说明
# 2026-07-31 - 小欧 - 三堂会审修复B17:注册循环加异常隔离,单个工具注册失败不阻断其余11个工具
# 2026-07-31 - 小欧 - 三堂会审增强:mouse_click描述/示例补clicks双击参数;keyboard_control描述与schema同步单键能力
"""

import importlib

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.logger import logger

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
    "clipboard_control": ["pyperclip"],
}

def check_pyautogui_available() -> bool:
    """检查pyautogui库是否可用 — 小健 2026-06-27"""
    try:
        importlib.import_module("pyautogui")
        return True
    except ImportError:
        return False


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
    ClipboardControlInput,
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
from app.tools.desktop.clipboard_control import clipboard_control


# 【描述规范】2026-07-20 北京老陈 — 工具描述(本 DESKTOP_TOOL_DESCRIPTIONS 字典)保持简洁、不冗余:
# 能力详情与默认支持的能力只写在对应 Schema 类的 docstring 里(会进入 JSON Schema 发给 LLM);
# 本字典仅作一句话路由/适用场景说明,严禁重复 schema docstring 内容。
DESKTOP_TOOL_DESCRIPTIONS = {
    "window_info": """列出当前系统所有可见窗口。可选include_minimized包含最小化窗口(默认False=不包含),filter_title按标题子串过滤。返回窗口列表(含标题/状态/位置)。适用场景:需要查看当前打开了哪些窗口、确认窗口名称时使用。""",

    "window_focus": """聚焦(激活)指定窗口,将其置于前台。window_title支持大小写不敏感的子串匹配。适用场景:需要将特定窗口切换到前台进行操作时使用。""",

    "window_resize": """调整指定窗口的大小。window_title为窗口标题,width/height为目标宽高(像素),传0保持原大小。适用场景:需要精确控制窗口尺寸时使用。""",

    "set_window_state": """窗口状态操作。action决定操作类型:maximize(最大化)/minimize(最小化)/restore(还原)/topmost(置顶)/unpin(取消置顶)。window_title支持大小写不敏感的子串匹配。适用场景:需要控制窗口显示状态时使用。""",

    "mouse_click": """在指定位置进行鼠标单击。x/y为屏幕绝对坐标(可选,不传则在当前位置点击),button为left/right/middle(默认left),clicks为点击次数(1=单击/2=双击,默认1)。适用场景:需要模拟点击按钮、选择菜单项、双击打开文件或单元格时使用。""",

    "mouse_move": """移动鼠标到指定屏幕坐标位置。x/y为屏幕绝对坐标(像素,左上角为原点)。适用场景:需要将鼠标移动到特定位置进行后续操作时使用。""",

    "mouse_scroll": """模拟鼠标滚轮滚动。direction为up/down(默认down),amount为滚动次数(每次约3行文本,默认3)。适用场景:需要滚动页面、浏览长文档时使用。""",

    "mouse_position": """获取鼠标当前的屏幕坐标位置。适用场景:需要确认鼠标当前位置、获取坐标用于后续点击/移动时使用。""",

    "keyboard_control": """键盘控制工具。action=type(输入文本)、shortcut(快捷键，支持组合键如ctrl+shift+esc)。适用场景:需要模拟键盘输入、执行快捷键操作时使用。""",

    "screen_capture": """截取屏幕截图,支持全屏、指定区域和多显示器。注意:display参数与region/dest互斥,指定display时不能传region或dest。适用场景:需要截取屏幕内容用于记录或传递给LLM分析时使用。""",

    "clipboard_control": """剪贴板操作。action决定操作类型:read(读取剪贴板内容)/write(写入内容到剪贴板)。action=write时content参数必填。适用场景:需要读取或写入剪贴板文本时使用。""",

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
    "clipboard_control": ClipboardControlInput,
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
        {"window_title": "Chrome", "width": 0, "height": 0},
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
        {"x": 500, "y": 300, "clicks": 2},
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
        {"action": "shortcut", "text_or_keys": "ctrl+c"},
        {"action": "shortcut", "text_or_keys": "alt+tab"},
        {"action": "shortcut", "text_or_keys": "ctrl+shift+esc"}
    ],
    "screen_capture": [
        {},
        {"region": {"x": 0, "y": 0, "width": 800, "height": 600}},
        {"display": 1},
        {"display": 2},
    ],
    "clipboard_control": [
        {"action": "read"},
        {"action": "write", "content": "Hello World"},
    ],
}


def _register_desktop_tools():
    """注册DESKTOP分类工具(11个) — 小健 2026-06-22 合并clipboard"""
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
        "clipboard_control": clipboard_control,
    }

    for name, method in tool_methods.items():
        desc = DESKTOP_TOOL_DESCRIPTIONS.get(name, "")
        input_model = DESKTOP_TOOL_INPUT_MODELS.get(name)
        examples = DESKTOP_TOOL_EXAMPLES.get(name, [])
        try:
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
        except Exception as e:
            logger.error(f"[desktop_register] 注册工具失败: {name}, 错误: {e}")
            continue
        logger.debug(
            f"[desktop_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )

__all__ = ["_register_desktop_tools"]
