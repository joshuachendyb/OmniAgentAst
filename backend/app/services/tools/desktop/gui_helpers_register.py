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

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要获取当前鼠标坐标时使用
- 当用户需要记录鼠标位置进行后续操作时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"x": 100, "y": 200}  # 不要传任何参数！

返回数据说明：
- code: 状态码，成功为"SUCCESS"，失败为"ERR_GET_MOUSE_POSITION"
- data: 成功时为{"x": int, "y": int}，失败时为None
- message: 结果描述信息""",
    "check_screen_size": """检查屏幕分辨率。

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要获取屏幕分辨率时使用
- 当用户在进行屏幕操作前需要了解屏幕尺寸时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"width": 1920}  # 不要传任何参数！

返回数据说明：
- code: 状态码，成功为"SUCCESS"，失败为"ERR_CHECK_SCREEN_SIZE"
- data: 成功时为{"width": int, "height": int}，失败时为None
- message: 结果描述信息""",
    "check_window_exists": """检查窗口是否存在。

使用场景：
- 当用户需要确认某个窗口是否打开时使用
- 当用户在进行窗口操作前需要验证窗口是否存在时使用


返回：
- exists: 窗口是否存在（true/false）

【重要】返回窗口是否存在（true/false）

使用示例：
- 检查窗口：{"title": "Chrome"}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，失败为"ERR_CHECK_WINDOW"
- data: 成功时为{"exists": bool}，失败时为None
- message: 结果描述信息""",
    "get_window_position": """获取窗口位置和大小。

使用场景：
- 当用户需要获取窗口的位置和尺寸时使用
- 当用户在进行窗口操作前需要了解窗口状态时使用


返回：
- x: 窗口 X 坐标
- y: 窗口 Y 坐标
- width: 窗口宽度
- height: 窗口高度

【重要】返回窗口的 X、Y 坐标和宽度、高度

使用示例：
- 获取窗口信息：{"title": "Chrome"}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，失败为"ERR_GET_WINDOW_POSITION"
- data: 成功时为{"x": int, "y": int, "width": int, "height": int}，窗口未找到时为None
- message: 结果描述信息""",
    "check_screen_capture_permission": """检查屏幕捕获权限。

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要确认是否有屏幕截图权限时使用
- 当用户在进行截屏或录屏前需要验证权限时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"permission": true}  # 不要传任何参数！

返回数据说明：
- code: 状态码，成功为"SUCCESS"，失败为"ERR_CHECK_PERMISSION"
- data: 成功时为{"has_permission": True}，失败时为{"has_permission": False}或None
- message: 结果描述信息""",
    "check_tesseract_available": """检查 Tesseract OCR 引擎是否可用。

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要确认 Tesseract OCR 引擎是否安装时使用
- 当用户在进行 OCR 识别前需要验证引擎是否可用时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"available": true}  # 不要传任何参数！

返回数据说明：
- code: 状态码，成功为"SUCCESS"，失败为"ERR_CHECK_TESSERACT"
- data: 成功时为{"is_available": bool}，失败时为None
- message: 结果描述信息""",
    "check_notification_permission": """检查系统通知权限。

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要确认是否有发送系统通知权限时使用
- 当用户在发送通知前需要验证权限时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"permission": true}  # 不要传任何参数！

返回数据说明：
- code: 状态码，成功为"SUCCESS"，失败为"ERR_CHECK_PERMISSION"
- data: 成功时为{"has_permission": True}，失败时为{"has_permission": False}或None
- message: 结果描述信息""",
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
    """【2026-05-17 小沈】已迁移到toolhelper/gui_helper.py（26→10精简方案）

    原GUI辅助工具(get_mouse_position等7个)不再作为LLM可见工具注册，
    已迁移到 toolhelper/gui_helper.py 作为内部辅助函数。
    本函数为空操作，防止旧调用报错。
    """
    from app.utils.logger import logger
    logger.info("[gui_helpers_register] GUI辅助工具已迁移到toolhelper/gui_helper.py，跳过注册")


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_gui_helpers"]