# -*- coding: utf-8 -*-
"""
GUI Register - GUI操作工具注册点

【架构规范】2026-05-02 小沈
- gui_register.py: 显式注册（tool_registry.register）
- gui_tools.py: 工具函数实现（无装饰器）
- gui_schema.py: Pydantic 模型

【2026-05-02 小沈重构】
- 从 @register_tool 装饰器注册改为显式注册（tool_registry.register）
- 按 shell_register.py 模式重写

创建时间: 2026-05-02
更新时间: 2026-05-02
"""

from app.services.tools.registry import tool_registry, ToolCategory
from app.utils.logger import logger

from app.services.tools.gui.gui_schema import (
    ClickInput,
    MoveInput,
    ScrollInput,
    TypeTextInput,
    ShortcutInput,
    KeyComboInput,
    ScreenshotInput,
    SnapshotInput,
    ScreenRecordInput,
    FocusWindowInput,
    ResizeWindowInput,
    OcrInput,
    ListWindowsInput,
    ReadClipboardInput,
    WriteClipboardInput,
    SendNotificationInput,
)

from app.services.tools.gui.gui_tools import (
    click,
    move,
    scroll,
    type_text,
    shortcut,
    key_combo,
    screenshot,
    snapshot,
    screen_record,
    list_windows,
    focus_window,
    resize_window,
    ocr,
    read_clipboard,
    write_clipboard,
    send_notification,
)

GUI_TOOL_DESCRIPTIONS = {
    "click": """模拟鼠标点击操作。

使用场景：
- 当用户需要模拟鼠标点击按钮或链接时使用
- 当用户需要进行桌面自动化操作时使用
- 当用户需要点击特定位置时使用

参数说明：
- x：点击的 X 坐标
- y：点击的 Y 坐标
- button：鼠标按钮（可选），可填 left/right/middle
- click_type：点击类型（可选），可填 single/double

【重要】需要安装 pyautogui 库（pip install pyautogui）""",
    "move": """移动鼠标到指定位置。

使用场景：
- 当用户需要移动鼠标到特定位置时使用
- 当用户需要进行桌面自动化操作时使用
- 当用户需要将鼠标悬停在特定元素上时使用

【重要】需要安装 pyautogui 库""",
    "scroll": """模拟鼠标滚轮滚动。

使用场景：
- 当用户需要滚动页面或文档时使用
- 当用户需要向下滚动查看更多内容时使用

参数说明：
- direction：滚动方向，可选 up/down
- amount：滚动单位数量（可选）

【重要】需要安装 pyautogui 库""",
    "type_text": """模拟键盘输入文本。

使用场景：
- 当用户需要在输入框中输入文本时使用
- 当用户需要进行表单填写自动化时使用

参数说明：
- text：要输入的文本
- interval：每个字符间隔（秒）（可选）

【重要】需要安装 pyautogui 库""",
    "shortcut": """执行键盘快捷键组合。

使用场景：
- 当用户需要执行快捷键操作时使用
- 当用户需要进行复制粘贴、保存等快捷操作时使用

参数说明：
- keys：快捷键组合（如 "ctrl+c", "alt+tab"）

【重要】需要安装 pyautogui 库""",
    "key_combo": """按住多个键后释放。

使用场景：
- 当用户需要按住多个键执行组合操作时使用
- 当用户需要精确控制按键按下和释放顺序时使用

参数说明：
- keys：要按住的键数组
- action：操作，可选 press/hold/release

【重要】需要安装 pyautogui 库""",
    "screenshot": """截取屏幕截图。

使用场景：
- 当用户需要截取当前屏幕画面时使用
- 当用户需要保存屏幕截图作为记录时使用

参数说明：
- output_path：输出文件路径（可选）
- region：截取区域 {x, y, width, height}

【重要】需要安装 pyautogui 或 PIL 库""",
    "snapshot": """获取完整桌面状态快照。

使用场景：
- 当用户需要获取当前桌面完整状态时使用
- 当用户需要进行桌面状态分析时使用

参数说明：
- display：显示器编号（可选）

【重要】需要安装 mss 或 PIL 库""",
    "screen_record": """录制屏幕视频。

使用场景：
- 当用户需要录制屏幕操作过程时使用
- 当用户需要制作操作教程或演示视频时使用

参数说明：
- duration：录制时长（秒）
- output_path：输出文件路径（可选）
- fps：帧率（可选）

【重要】需要安装屏幕录制库（mss + PIL）""",
    "list_windows": """获取所有打开的窗口列表。

使用场景：
- 当用户需要查看当前打开的所有窗口时使用
- 当用户需要查找特定窗口时使用

参数说明：
- filter：窗口标题过滤

【重要】需要安装 pywin32 库（Windows）""",
    "focus_window": """聚焦指定窗口。

使用场景：
- 当用户需要将特定窗口置为前台时使用
- 当用户需要激活某个窗口进行操作时使用

参数说明：
- title：窗口标题

【重要】需要安装 pywin32 库""",
    "resize_window": """调整窗口大小。

使用场景：
- 当用户需要调整窗口大小时使用
- 当用户需要将窗口设置为特定尺寸时使用

参数说明：
- title：窗口标题
- width：宽度
- height：高度

【重要】需要安装 pywin32 库""",
    "ocr": """从图片中识别文字。

使用场景：
- 当用户需要从图片中提取文字内容时使用
- 当用户需要进行图片文字识别（OCR）时使用

参数说明：
- image_path：图片文件路径
- language：识别语言，可选 eng/chi_sim/eng+chi_sim

【重要】需要安装 pytesseract 库和 Tesseract OCR 引擎""",
    "read_clipboard": """读取剪贴板内容。

使用场景：
- 当用户需要获取剪贴板中的文本时使用
- 当用户需要读取复制的内容时使用

参数说明：
- 无参数

【重要】使用 pyperclip 库或零依赖的 ctypes""",
    "write_clipboard": """写入内容到剪贴板。

使用场景：
- 当用户需要将文本复制到剪贴板时使用
- 当用户需要准备数据供用户粘贴时使用

参数说明：
- text：要写入的内容（必填）

【重要】使用 pyperclip 库或零依赖的 ctypes""",
    "send_notification": """发送 Windows 系统通知。

使用场景：
- 当用户需要发送系统通知提醒时使用
- 当用户需要通知用户某个操作完成时使用

参数说明：
- title：通知标题（必填）
- message：通知内容（必填）
- duration：显示时长（可选），默认5秒

【重要】需要安装 win10toast 库（Windows专用）""",
}

GUI_TOOL_EXAMPLES = {
    "click": [
        {"x": 500, "y": 300},
        {"x": 500, "y": 300, "click_type": "double"},
    ],
    "move": [
        {"x": 500, "y": 300},
        {"x": 500, "y": 300, "duration": 1.5},
    ],
    "scroll": [
        {"direction": "down"},
        {"direction": "up", "amount": 10},
    ],
    "type_text": [
        {"text": "Hello World"},
        {"text": "Hello", "interval": 0.1},
    ],
    "shortcut": [
        {"keys": "ctrl+c"},
        {"keys": "alt+tab"},
    ],
    "key_combo": [
        {"keys": ["ctrl", "c"], "action": "press"},
        {"keys": ["ctrl", "shift"], "action": "hold"},
    ],
    "screenshot": [
        {},
        {"output_path": "D:/output/region.png", "region": {"x": 0, "y": 0, "width": 800, "height": 600}},
    ],
    "snapshot": [
        {},
        {"display": 2},
    ],
    "screen_record": [
        {"duration": 30},
        {"duration": 60, "output_path": "D:/output/demo.mp4", "fps": 30},
    ],
    "list_windows": [
        {},
        {"filter": "Chrome"},
    ],
    "focus_window": [
        {"title": "Chrome"},
    ],
    "resize_window": [
        {"title": "Chrome", "width": 1920, "height": 1080},
    ],
    "ocr": [
        {"image_path": "D:/images/screenshot.png"},
        {"image_path": "D:/images/screenshot.png", "language": "chi_sim"},
    ],
    "read_clipboard": [
        {},
    ],
    "write_clipboard": [
        {"text": "要复制的文本内容"},
    ],
    "send_notification": [
        {"title": "任务完成", "message": "文件已成功保存"},
        {"title": "提醒", "message": "请检查结果", "duration": 10},
    ],
}


def _register_gui_tools():
    """
    【2026-05-02 小沈】显式注册所有GUI工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "click": click,
        "move": move,
        "scroll": scroll,
        "type_text": type_text,
        "shortcut": shortcut,
        "key_combo": key_combo,
        "screenshot": screenshot,
        "snapshot": snapshot,
        "screen_record": screen_record,
        "list_windows": list_windows,
        "focus_window": focus_window,
        "resize_window": resize_window,
        "ocr": ocr,
        "read_clipboard": read_clipboard,
        "write_clipboard": write_clipboard,
        "send_notification": send_notification,
    }

    TOOL_INPUT_MODELS = {
        "click": ClickInput,
        "move": MoveInput,
        "scroll": ScrollInput,
        "type_text": TypeTextInput,
        "shortcut": ShortcutInput,
        "key_combo": KeyComboInput,
        "screenshot": ScreenshotInput,
        "snapshot": SnapshotInput,
        "screen_record": ScreenRecordInput,
        "list_windows": ListWindowsInput,
        "focus_window": FocusWindowInput,
        "resize_window": ResizeWindowInput,
        "ocr": OcrInput,
        "read_clipboard": ReadClipboardInput,
        "write_clipboard": WriteClipboardInput,
        "send_notification": SendNotificationInput,
    }

    for name, method in tool_methods.items():
        desc = GUI_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = GUI_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.GUI,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(f"[gui_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


_register_gui_tools()


__all__ = [
    "click", "move", "scroll",
    "type_text", "shortcut", "key_combo",
    "screenshot", "snapshot", "screen_record",
    "list_windows", "focus_window", "resize_window",
    "ocr", "read_clipboard", "write_clipboard", "send_notification",
]
