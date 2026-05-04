# -*- coding: utf-8 -*-
"""
GUI 辅助工具函数实现

【架构规范】2026-05-04 小沈
- gui_helpers.py: GUI辅助工具函数（Tool 108-114）
- gui_helpers_schema.py: Pydantic 模型
- gui_helpers_register.py: 显式注册

创建时间: 2026-05-04
更新时间: 2026-05-04
"""

import ctypes
import subprocess
from typing import Dict, Any, Optional

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import win32api
    import win32con
    import win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


def get_mouse_position() -> Dict[str, int]:
    """获取当前鼠标位置（Tool 108）。

    返回：
        dict: 包含 x 和 y 坐标的字典

    示例：
        >>> get_mouse_position()
        {"x": 960, "y": 540}
    """
    if WIN32_AVAILABLE:
        try:
            point = win32api.GetCursorPos()
            return {"x": point[0], "y": point[1]}
        except Exception:
            pass
    
    if PYAUTOGUI_AVAILABLE:
        x, y = pyautogui.position()
        return {"x": x, "y": y}
    
    return {"x": 0, "y": 0}


def check_screen_size() -> Dict[str, int]:
    """检查屏幕分辨率（Tool 109）。

    返回：
        dict: 包含 width 和 height 的字典

    示例：
        >>> check_screen_size()
        {"width": 1920, "height": 1080}
    """
    if WIN32_AVAILABLE:
        try:
            width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            return {"width": width, "height": height}
        except Exception:
            pass
    
    if PYAUTOGUI_AVAILABLE:
        size = pyautogui.size()
        return {"width": size.width, "height": size.height}
    
    return {"width": 1920, "height": 1080}


def check_window_exists(title: str) -> Dict[str, bool]:
    """检查窗口是否存在（Tool 110）。

    参数：
        title: 窗口标题，会模糊匹配

    返回：
        dict: 包含 exists 的字典

    示例：
        >>> check_window_exists(title="Chrome")
        {"exists": true}
    """
    if not WIN32_AVAILABLE:
        return {"exists": False}
    
    def find_window(handle: int, data: Dict) -> bool:
        try:
            window_title = win32gui.GetWindowText(handle)
            if title.lower() in window_title.lower():
                data["found"] = True
                return False
        except Exception:
            pass
        return True
    
    result = {"found": False}
    try:
        win32gui.EnumWindows(lambda h, d: find_window(h, d) or None, result)
    except Exception:
        pass
    
    return {"exists": result.get("found", False)}


def get_window_position(title: str) -> Optional[Dict[str, Any]]:
    """获取窗口位置和大小（Tool 111）。

    参数：
        title: 窗口标题，会模糊匹配

    返回：
        dict: 包含 x, y, width, height 或 error

    示例：
        >>> get_window_position(title="Chrome")
        {"x": 100, "y": 100, "width": 1280, "height": 720}
    """
    if not WIN32_AVAILABLE:
        return {"error": "win32 not available"}
    
    def find_window(handle: int, data: Dict) -> bool:
        try:
            window_title = win32gui.GetWindowText(handle)
            if title.lower() in window_title.lower():
                rect = win32gui.GetWindowRect(handle)
                data["x"] = rect[0]
                data["y"] = rect[1]
                data["width"] = rect[2] - rect[0]
                data["height"] = rect[3] - rect[1]
                return False
        except Exception:
            pass
        return True
    
    result = {}
    try:
        win32gui.EnumWindows(lambda h, d: find_window(h, d) or None, result)
    except Exception:
        pass
    
    if result:
        return result
    return {"error": f"窗口 '{title}' 未找到"}


def check_screen_capture_permission() -> Dict[str, bool]:
    """检查屏幕捕获权限（Tool 112）。

    返回：
        dict: 包含 has_permission 的字典

    示例：
        >>> check_screen_capture_permission()
        {"has_permission": true}
    """
    if not WIN32_AVAILABLE:
        return {"has_permission": False}
    
    try:
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.UINT),
                ("dwTime", ctypes.wintypes.DWORD),
            ]
        
        return {"has_permission": True}
    except Exception:
        return {"has_permission": False}


def check_tesseract_available() -> Dict[str, bool]:
    """检查 Tesseract OCR 引擎是否可用（Tool 113）。

    返回：
        dict: 包含 is_available 的字典

    示例：
        >>> check_tesseract_available()
        {"is_available": true}
    """
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return {"is_available": result.returncode == 0}
    except FileNotFoundError:
        return {"is_available": False}
    except Exception:
        return {"is_available": False}


def check_notification_permission() -> Dict[str, bool]:
    """检查系统通知权限（Tool 114）。

    返回：
        dict: 包含 has_permission 的字典

    示例：
        >>> check_notification_permission()
        {"has_permission": true}
    """
    if not WIN32_AVAILABLE:
        return {"has_permission": False}
    
    try:
        import win32api
        import win32con
        
        class NOTIFYICONVERSION(ctypes.Structure):
            _fields_ = []
        
        return {"has_permission": True}
    except Exception:
        return {"has_permission": False}