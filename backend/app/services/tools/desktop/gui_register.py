# 
"""
GUI Register - GUI操作工具注册点

【架构规范】2026-05-02 小沈
- gui_register.py: 显式注册（tool_registry.register）
- gui_tools.py: 工具函数实现（无装饰器）
- gui_schema.py: Pydantic 模型

【2026-05-02 小沈重构】
- 从 @register_tool 装饰器注册改为显式注册（tool_registry.register）
- 按 shell_register.py 模式重写

# GUI操作工具（共16个） 小沈-2026-05-05

创建时间: 2026-05-02
更新时间: 2026-05-09
"""

from app.services.tools.registry import tool_registry, ToolCategory
from app.utils.logger import logger

from app.services.tools.desktop.gui_schema import (
    ScreenRecordInput,
    OcrInput,
    SendNotificationInput,
)

from app.services.tools.desktop.gui_tools import (
    screen_record,
    ocr,
    send_notification,
)

GUI_TOOL_DESCRIPTIONS = {
    "click": """模拟鼠标点击操作。

使用场景：
- 当用户需要模拟鼠标点击按钮或链接时使用
- 当用户需要进行桌面自动化操作时使用
- 当用户需要点击特定位置时使用


【重要】需要安装 pyautogui 库

使用示例：
- 单击左键：{"x": 500, "y": 300}
- 双击：{"x": 500, "y": 300, "click_type": "double"}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_PYAUTOGUI"，操作失败为"ERR_CLICK"
- data: 成功时为{"x": int, "y": int, "button": str, "click_type": str}（点击坐标、鼠标按钮、点击类型），失败时为null
- message: 状态描述信息""",
    "move": """移动鼠标到指定位置。

使用场景：
- 当用户需要移动鼠标到特定位置时使用
- 当用户需要进行桌面自动化操作时使用
- 当用户需要将鼠标悬停在特定元素上时使用


【重要】需要安装 pyautogui 库

使用示例：
- 瞬间移动：{"x": 500, "y": 300}
- 平滑移动：{"x": 500, "y": 300, "duration": 1.5}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_PYAUTOGUI"，操作失败为"ERR_MOVE"
- data: 成功时为{"x": int, "y": int}（鼠标移动到的坐标），失败时为null
- message: 状态描述信息""",
    "scroll": """模拟鼠标滚轮滚动。

使用场景：
- 当用户需要滚动页面或文档时使用
- 当用户需要向下滚动查看更多内容时使用
- 当用户需要向上滚动回到顶部时使用


【重要】需要安装 pyautogui 库

使用示例：
- 向下滚动：{"direction": "down"}
- 向上滚动10单位：{"direction": "up", "amount": 10}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_PYAUTOGUI"，操作失败为"ERR_DESKTOP_SCROLL"
- data: 成功时为{"direction": str, "amount": int}（滚动方向和单位数），失败时为null
- message: 状态描述信息""",
    "type_text": """模拟键盘输入文本。

使用场景：
- 当用户需要在输入框中输入文本时使用
- 当用户需要进行表单填写自动化时使用
- 当用户需要模拟键盘打字时使用


【重要】需要安装 pyautogui 或 keyboard 库

使用示例：
- 快速输入：{"text": "Hello World"}
- 模拟打字：{"text": "Hello", "interval": 0.1}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_PYAUTOGUI"，操作失败为"ERR_KEYBOARD_TYPE"
- data: 成功时为{"text_length": int}（已输入的字符数），失败时为null
- message: 状态描述信息""",
    "shortcut": """执行键盘快捷键组合。

使用场景：
- 当用户需要执行快捷键操作时使用
- 当用户需要进行复制粘贴、保存等快捷操作时使用
- 当用户需要切换窗口或程序时使用


【重要】需要安装 pyautogui 或 keyboard 库

使用示例：
- 复制：{"keys": "ctrl+c"}
- 切换窗口：{"keys": "alt+tab"}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_PYAUTOGUI"，操作失败为"ERR_KEYBOARD_SHORTCUT"
- data: 成功时为{"keys": str}（执行的快捷键组合），失败时为null
- message: 状态描述信息""",
    "key_combo": """按住多个键后释放。

使用场景：
- 当用户需要按住多个键执行组合操作时使用
- 当用户需要自定义按键组合时使用
- 当用户需要精确控制按键按下和释放顺序时使用


【重要】需要安装 pyautogui 或 keyboard 库

使用示例：
- 按下并释放：{"keys": ["ctrl", "c"], "action": "press"}
- 按住不放：{"keys": ["ctrl", "shift"], "action": "hold"}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_PYAUTOGUI"，操作失败为"ERR_KEY_COMBO"
- data: 成功时为{"keys": list, "action": str}（按键列表和执行动作"press"/"hold"/"release"），失败时为null
- message: 状态描述信息""",
    "screenshot": """截取屏幕截图。

使用场景：
- 当用户需要截取当前屏幕画面时使用
- 当用户需要保存屏幕截图作为记录时使用
- 当用户需要截取特定区域画面时使用


【重要】需要安装 mss 或 PIL 库

使用示例：
- 截取全屏：{}
- 截取区域：{"output_path": "D:/output/region.png", "region": {"x": 0, "y": 0, "width": 800, "height": 600}}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_PYAUTOGUI"，操作失败为"ERR_SCREENSHOT"
- data: 成功时为str（截图保存的文件路径），失败时为null
- message: 状态描述信息""",
    "snapshot": """获取完整桌面状态快照。

使用场景：
- 当用户需要获取当前桌面完整状态时使用
- 当用户需要记录桌面当前所有窗口和元素时使用
- 当用户需要进行桌面状态分析时使用


【重要】需要安装 mss 或 PIL 库

使用示例：
- 获取主显示器快照：{}
- 获取第二显示器：{"display": 2}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_SCREENSHOT_LIB"，操作失败为"ERR_SCREEN_SNAPSHOT"
- data: 成功时为{"image_path": str, "display": int}或{"image_path": str, "display": int, "monitors": int}（快照路径、显示器编号、显示器数量），失败时为null
- message: 状态描述信息""",
    "screen_record": """录制屏幕视频。

使用场景：
- 当用户需要录制屏幕操作过程时使用
- 当用户需要制作操作教程或演示视频时使用
- 当用户需要记录屏幕变化过程时使用


【重要】需要安装屏幕录制库（mss + PIL）

使用示例：
- 录制30秒：{"duration": 30}
- 高清录制：{"duration": 60, "output_path": "D:/output/demo.mp4", "fps": 30}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_RECORD_LIB"/"ERR_NO_NUMPY"/"ERR_NO_IMAGEIO"，操作失败为"ERR_SCREEN_RECORD"
- data: 成功时为{"output_path": str, "duration": int, "fps": int}（视频保存路径、录制时长、帧率），失败时为null
- message: 状态描述信息""",
    "list_windows": """获取所有打开的窗口列表。

使用场景：
- 当用户需要查看当前打开的所有窗口时使用
- 当用户需要查找特定窗口时使用
- 当用户需要了解当前桌面窗口状态时使用


【重要】需要安装 pywin32 库

使用示例：
- 获取全部窗口：{}
- 过滤Chrome窗口：{"filter": "Chrome"}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_WIN32GUI"，操作失败为"ERR_LIST_WINDOWS"
- data: 成功时为{"windows": [{"hwnd": int, "title": str}, ...], "count": int}（窗口句柄与标题列表、窗口总数），失败时为null
- message: 状态描述信息""",
    "focus_window": """聚焦指定窗口。

使用场景：
- 当用户需要将特定窗口置为前台时使用
- 当用户需要激活某个窗口进行操作时使用
- 当用户需要切换到特定程序窗口时使用


【重要】需要安装 pywin32 库

使用示例：
- 聚焦窗口：{"title": "Chrome"}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_WIN32GUI"，窗口未找到为"ERR_WINDOW_NOT_FOUND"，操作失败为"ERR_FOCUS_WINDOW"
- data: 成功时为{"title": str, "hwnd": int}（窗口标题和句柄），失败时为null
- message: 状态描述信息""",
    "resize_window": """调整窗口大小。

使用场景：
- 当用户需要调整窗口大小时使用
- 当用户需要将窗口设置为特定尺寸时使用
- 当用户需要进行窗口布局自动化时使用


【重要】需要安装 pywin32 库

使用示例：
- 调整窗口：{"title": "Chrome", "width": 1920, "height": 1080}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_WIN32GUI"，窗口未找到为"ERR_WINDOW_NOT_FOUND"，操作失败为"ERR_WINDOW_RESIZE"
- data: 成功时为{"title": str, "width": int, "height": int}（窗口标题和调整后的宽高），失败时为null
- message: 状态描述信息""",
    "ocr": """从图片中识别文字。

使用场景：
- 当用户需要从图片中提取文字内容时使用
- 当用户需要进行图片文字识别（OCR）时使用
- 当用户需要识别截图中的文字时使用


【重要】需要安装 pytesseract 库和 Tesseract OCR 引擎

使用示例：
- 英文识别：{"image_path": "D:/images/screenshot.png"}
- 中文识别：{"image_path": "D:/images/screenshot.png", "language": "chi_sim"}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_TESSERACT"，操作失败为"ERR_OCR"
- data: 成功时为{"text": str, "language": str, "char_count": int}（识别的文本内容、使用的语言、字符数），失败时为null
- message: 状态描述信息""",
    "read_clipboard": """读取剪贴板内容。

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要获取剪贴板中的文本时使用
- 当用户需要读取复制的内容时使用
- 当用户需要获取剪贴板数据进行后续处理时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"text": "xxx"}  # 不要传任何参数！

返回数据说明：
- code: 状态码，成功为"SUCCESS"，操作失败为"ERR_CLIPBOARD"
- data: 成功时为{"text": str}（剪贴板中的文本内容），失败时为null
- message: 状态描述信息""",
    "write_clipboard": """写入内容到剪贴板。

使用场景：
- 当用户需要将文本复制到剪贴板时使用
- 当用户需要准备数据供用户粘贴时使用
- 当用户需要进行剪贴板自动化操作时使用


【重要】使用 pyperclip 库或零依赖的 ctypes

使用示例：
- 写入文本：{"content": "Hello World"}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，操作失败为"ERR_CLIPBOARD"
- data: 成功时为{"content": str}（写入剪贴板的文本内容），失败时为null
- message: 状态描述信息""",
    "send_notification": """发送 Windows 系统通知。

使用场景：
- 当用户需要发送系统通知提醒时使用
- 当用户需要通知用户某个操作完成时使用
- 当用户需要显示重要信息时使用


【重要】需要安装 win10toast 库

使用示例：
- 发送通知：{"title": "任务完成", "message": "数据处理已完成"}
- 自定义时长：{"title": "提醒", "message": "请检查数据", "duration": 10}

返回数据说明：
- code: 状态码，成功为"SUCCESS"，库缺失为"ERR_NO_WIN10TOAST"
- data: 成功时为{"title": str, "message": str, "duration": int}（通知标题、内容、显示时长），失败时为null
- message: 状态描述信息""",
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
        {"content": "要复制的文本内容"},
    ],
    "send_notification": [
        {"title": "任务完成", "message": "文件已成功保存"},
        {"title": "提醒", "message": "请检查结果", "duration": 10},
    ],
}


def _register_gui_tools():
    """
    【2026-05-17 小沈】已迁移到统一DESKTOP分类（26→10精简方案）
    原GUI工具已合并到 window_control / mouse_control / keyboard_control / screen_capture / clipboard_control
    保留 screen_record / ocr / send_notification 在统一DESKTOP注册中
    本函数为空操作，防止旧调用报错
    """
    from app.utils.logger import logger
    logger.info("[gui_register] GUI工具已迁移到统一DESKTOP分类，跳过注册")


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_gui_tools"]
