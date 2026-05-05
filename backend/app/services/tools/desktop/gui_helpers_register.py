# -*- coding: utf-8 -*-
"""
GUI 辅助工具注册点

【架构规范】2026-05-04 小沈
- gui_helpers_register.py: 显式注册（tool_registry.register）
- gui_helpers.py: 工具函数实现（无装饰器）
- gui_helpers_schema.py: Pydantic 模型

创建时间: 2026-05-04
更新时间: 2026-05-04
"""

from app.services.tools.registry import tool_registry, ToolCategory
from app.utils.logger import logger

from app.services.tools.desktop.gui_helpers_schema import (
    GetMousePositionInput,
    CheckScreenSizeInput,
    CheckWindowExistsInput,
    GetWindowPositionInput,
    CheckScreenCapturePermissionInput,
    CheckTesseractAvailableInput,
    CheckNotificationPermissionInput,
)

from app.services.tools.desktop.gui_helpers import (
    get_mouse_position,
    check_screen_size,
    check_window_exists,
    get_window_position,
    check_screen_capture_permission,
    check_tesseract_available,
    check_notification_permission,
)

GUI_HELPERS_DESCRIPTIONS = {
    "get_mouse_position": """获取当前鼠标位置。

使用场景：
- 当用户需要获取当前鼠标坐标时使用
- 当用户需要记录鼠标位置进行后续操作时使用

参数说明：
- 无参数

返回：
- x: 鼠标 X 坐标
- y: 鼠标 Y 坐标

【重要】返回鼠标的 X 和 Y 坐标

使用示例：
- 获取位置：{}""",
    "check_screen_size": """检查屏幕分辨率。

使用场景：
- 当用户需要获取屏幕分辨率时使用
- 当用户在进行屏幕操作前需要了解屏幕尺寸时使用

参数说明：
- 无参数

返回：
- width: 屏幕宽度（像素）
- height: 屏幕高度（像素）

【重要】返回屏幕的宽度和高度（像素）

使用示例：
- 获取分辨率：{}""",
    "check_window_exists": """检查窗口是否存在。

使用场景：
- 当用户需要确认某个窗口是否打开时使用
- 当用户在进行窗口操作前需要验证窗口是否存在时使用

参数说明：
- title：窗口标题（模糊匹配）

返回：
- exists: 窗口是否存在（true/false）

【重要】返回窗口是否存在（true/false）

使用示例：
- 检查窗口：{"title": "Chrome"}""",
    "get_window_position": """获取窗口位置和大小。

使用场景：
- 当用户需要获取窗口的位置和尺寸时使用
- 当用户在进行窗口操作前需要了解窗口状态时使用

参数说明：
- title：窗口标题（模糊匹配）

返回：
- x: 窗口 X 坐标
- y: 窗口 Y 坐标
- width: 窗口宽度
- height: 窗口高度

【重要】返回窗口的 X、Y 坐标和宽度、高度

使用示例：
- 获取窗口信息：{"title": "Chrome"}""",
    "check_screen_capture_permission": """检查屏幕捕获权限。

使用场景：
- 当用户需要确认是否有屏幕截图权限时使用
- 当用户在进行截屏或录屏前需要验证权限时使用

参数说明：
- 无参数

返回：
- has_permission: 是否有屏幕捕获权限

【重要】返回是否有屏幕捕获权限（true/false）

使用示例：
- 检查权限：{}""",
    "check_tesseract_available": """检查 Tesseract OCR 引擎是否可用。

使用场景：
- 当用户需要确认 Tesseract OCR 引擎是否安装时使用
- 当用户在进行 OCR 识别前需要验证引擎是否可用时使用

参数说明：
- 无参数

返回：
- is_available: Tesseract 是否可用

【重要】返回 Tesseract OCR 引擎是否可用（true/false）

使用示例：
- 检查引���：{}""",
    "check_notification_permission": """检查系统通知权限。

使用场景：
- 当用户需要确认是否有发送系统通知权限时使用
- 当用户在发送通知前需要验证权限时使用

参数说明：
- 无参数

返回：
- has_permission: 是否有通知权限

【重要】返回是否有系统通知权限（true/false）

使用示例：
- 检查权限：{}""",
}

GUI_HELPERS_EXAMPLES = {
    "get_mouse_position": [{}],
    "check_screen_size": [{}],
    "check_window_exists": [
        {"title": "Chrome"},
        {"title": "Notepad"},
    ],
    "get_window_position": [
        {"title": "Chrome"},
        {"title": "Notepad"},
    ],
    "check_screen_capture_permission": [{}],
    "check_tesseract_available": [{}],
    "check_notification_permission": [{}],
}


def _register_gui_helpers():
    """【2026-05-04 小沈】显式注册所有GUI辅助工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "get_mouse_position": get_mouse_position,
        "check_screen_size": check_screen_size,
        "check_window_exists": check_window_exists,
        "get_window_position": get_window_position,
        "check_screen_capture_permission": check_screen_capture_permission,
        "check_tesseract_available": check_tesseract_available,
        "check_notification_permission": check_notification_permission,
    }

    TOOL_INPUT_MODELS = {
        "get_mouse_position": GetMousePositionInput,
        "check_screen_size": CheckScreenSizeInput,
        "check_window_exists": CheckWindowExistsInput,
        "get_window_position": GetWindowPositionInput,
        "check_screen_capture_permission": CheckScreenCapturePermissionInput,
        "check_tesseract_available": CheckTesseractAvailableInput,
        "check_notification_permission": CheckNotificationPermissionInput,
    }

    for name, method in tool_methods.items():
        desc = GUI_HELPERS_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = GUI_HELPERS_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.GUI,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(f"[gui_helpers_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


_register_gui_helpers()


__all__ = [
    "get_mouse_position",
    "check_screen_size",
    "check_window_exists",
    "get_window_position",
    "check_screen_capture_permission",
    "check_tesseract_available",
    "check_notification_permission",
]