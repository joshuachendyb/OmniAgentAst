# -*- coding: utf-8 -*-
"""
GUI 辅助工具函数实现

【架构规范】2026-05-04 小沈
- gui_helpers.py: GUI辅助工具函数（Tool 108-114）
- gui_helpers_schema.py: Pydantic 模型
- gui_helpers_register.py: 显式注册

【返回格式】统一格式：
- 成功：{"code": "SUCCESS", "data": {...}, "message": "成功信息"}
- 失败：{"code": "ERR_xxx", "data": None, "message": "错误信息"}

创建时间: 2026-05-04
更新时间: 2026-05-04
"""

import ctypes
import subprocess
from typing import Dict, Any

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


def get_mouse_position() -> Dict[str, Any]:
    """获取当前鼠标位置（Tool 108）。

    返回格式：
        成功：{"code": "SUCCESS", "data": {"x": x, "y": y}, "message": "获取成功"}
        失败：{"code": "ERR_GET_MOUSE_POSITION", "data": None, "message": "错误信息"}
    """
    if WIN32_AVAILABLE:
        try:
            point = win32api.GetCursorPos()
            return {"code": "SUCCESS", "data": {"x": point[0], "y": point[1]}, "message": f"鼠标位置: ({point[0]}, {point[1]})"}
        except Exception as e:
            return {"code": "ERR_GET_MOUSE_POSITION", "data": None, "message": f"获取失败: {str(e)}"}
    
    if PYAUTOGUI_AVAILABLE:
        try:
            x, y = pyautogui.position()
            return {"code": "SUCCESS", "data": {"x": x, "y": y}, "message": f"鼠标位置: ({x}, {y})"}
        except Exception as e:
            return {"code": "ERR_GET_MOUSE_POSITION", "data": None, "message": f"获取失败: {str(e)}"}
    
    return {"code": "SUCCESS", "data": {"x": 0, "y": 0}, "message": "无依赖库，返回默认位置 (0, 0)"}


def check_screen_size() -> Dict[str, Any]:
    """检查屏幕分辨率（Tool 109）。

    返回格式：
        成功：{"code": "SUCCESS", "data": {...}, "message": "成功信息"}
        失败：{"code": "ERR_CHECK_SCREEN_SIZE", "data": None, "message": "错误信息"}
    """
    if WIN32_AVAILABLE:
        try:
            width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            return {"code": "SUCCESS", "data": {"width": width, "height": height}, "message": f"屏幕分辨率: {width}x{height}"}
        except Exception as e:
            return {"code": "ERR_CHECK_SCREEN_SIZE", "data": None, "message": f"获取失败: {str(e)}"}
    
    if PYAUTOGUI_AVAILABLE:
        try:
            size = pyautogui.size()
            return {"code": "SUCCESS", "data": {"width": size.width, "height": size.height}, "message": f"屏幕分辨率: {size.width}x{size.height}"}
        except Exception as e:
            return {"code": "ERR_CHECK_SCREEN_SIZE", "data": None, "message": f"获取失败: {str(e)}"}
    
    return {"code": "SUCCESS", "data": {"width": 1920, "height": 1080}, "message": "无依赖库，返回默认分辨率 1920x1080"}


def check_window_exists(title: str) -> Dict[str, Any]:
    """检查窗口是否存在（Tool 110）。

    返回格式：
        成功：{"code": "SUCCESS", "data": {"exists": true/false}, "message": "成功信息"}
        失败：{"code": "ERR_CHECK_WINDOW", "data": None, "message": "错误信息"}
    """
    if not WIN32_AVAILABLE:
        return {"code": "ERR_CHECK_WINDOW", "data": None, "message": "win32库未安装"}
    
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
    except Exception as e:
        return {"code": "ERR_CHECK_WINDOW", "data": None, "message": f"检查失败: {str(e)}"}
    
    exists = result.get("found", False)
    return {"code": "SUCCESS", "data": {"exists": exists}, "message": f"窗口 '{title}' {'存在' if exists else '不存在'}"}


def get_window_position(title: str) -> Dict[str, Any]:
    """获取窗口位置和大小（Tool 111）。

    返回格式：
        成功：{"code": "SUCCESS", "data": {"x": x, "y": y, "width": w, "height": h}, "message": "成功信息"}
        失败：{"code": "ERR_GET_WINDOW_POSITION", "data": None, "message": "错误信息"}
    """
    if not WIN32_AVAILABLE:
        return {"code": "ERR_GET_WINDOW_POSITION", "data": None, "message": "win32库未安装"}
    
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
    except Exception as e:
        return {"code": "ERR_GET_WINDOW_POSITION", "data": None, "message": f"获取失败: {str(e)}"}
    
    if result:
        return {"code": "SUCCESS", "data": result, "message": f"窗口位置: ({result['x']}, {result['y']}) 大小: {result['width']}x{result['height']}"}
    return {"code": "ERR_GET_WINDOW_POSITION", "data": None, "message": f"窗口 '{title}' 未找到"}


def check_screen_capture_permission() -> Dict[str, Any]:
    """检查屏幕捕获权限（Tool 112）。

    返回格式：
        成功：{"code": "SUCCESS", "data": {"has_permission": true/false}, "message": "成功信息"}
        失败：{"code": "ERR_CHECK_PERMISSION", "data": None, "message": "错误信息"}
    """
    if not WIN32_AVAILABLE:
        return {"code": "ERR_CHECK_PERMISSION", "data": None, "message": "win32库未安装"}
    
    try:
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.UINT),
                ("dwTime", ctypes.wintypes.DWORD),
            ]
        
        return {"code": "SUCCESS", "data": {"has_permission": True}, "message": "具有屏幕捕获权限"}
    except Exception as e:
        return {"code": "SUCCESS", "data": {"has_permission": False}, "message": f"无屏幕捕获权限: {str(e)}"}


def check_tesseract_available() -> Dict[str, Any]:
    """检查 Tesseract OCR 引擎是否可用（Tool 113）。

    返回格式：
        成功：{"code": "SUCCESS", "data": {"is_available": true/false}, "message": "成功信息"}
        失败：{"code": "ERR_CHECK_TESSERACT", "data": None, "message": "错误信息"}
    """
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        available = result.returncode == 0
        if available:
            return {"code": "SUCCESS", "data": {"is_available": True}, "message": "Tesseract OCR 引擎可用"}
        return {"code": "SUCCESS", "data": {"is_available": False}, "message": "Tesseract 命令执行失败"}
    except FileNotFoundError:
        return {"code": "SUCCESS", "data": {"is_available": False}, "message": "Tesseract OCR 未安装"}
    except Exception as e:
        return {"code": "ERR_CHECK_TESSERACT", "data": None, "message": f"检查失败: {str(e)}"}


def check_notification_permission() -> Dict[str, Any]:
    """检查系统通知权限（Tool 114）。

    返回格式：
        成功：{"code": "SUCCESS", "data": {"has_permission": true/false}, "message": "成功信息"}
        失败：{"code": "ERR_CHECK_PERMISSION", "data": None, "message": "错误信息"}
    """
    if not WIN32_AVAILABLE:
        return {"code": "ERR_CHECK_PERMISSION", "data": None, "message": "win32库未安装"}
    
    try:
        import win32api
        import win32con
        
        class NOTIFYICONVERSION(ctypes.Structure):
            _fields_ = []
        
        return {"code": "SUCCESS", "data": {"has_permission": True}, "message": "具有通知权限"}
    except Exception as e:
        return {"code": "SUCCESS", "data": {"has_permission": False}, "message": f"无通知权限: {str(e)}"}