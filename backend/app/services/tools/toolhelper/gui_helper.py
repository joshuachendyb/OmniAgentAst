# -*- coding: utf-8 -*-
"""
GUI Helper - GUI内部辅助函数集合（不暴露给LLM）

【创建时间】2026-05-17 小沈
【设计依据】按工具精简方案13.6节，将gui_helpers的7个检查函数迁移到此

包含：
- _require_gui_lib(lib_name): 检查GUI库是否可用
- _gui_safe_call(lib_name, error_msg, func, *args, **kwargs): 统一GUI安全调用包装
- _get_mouse_position(): 获取鼠标位置
- _check_screen_size(): 检查屏幕尺寸
- _check_window_exists(window_title): 检查窗口是否存在
- _get_window_position(window_title): 获取窗口位置
- _check_capture_permission(): 检查截屏权限
- _check_tesseract_available(): 检查OCR引擎
- _check_notification_permission(): 检查通知权限
- find_windows_by_title(title): 按标题查找窗口（从window_helper导入）

Author: 小沈 - 2026-05-17
"""

import ctypes
import importlib
import subprocess
from typing import Any, Callable, Dict, List, Optional

from app.services.agent.tool_result_utils import create_tool_result
from app.utils.logger import logger
from app.services.tools.toolhelper.window_helper import find_windows_by_title





def _require_gui_lib(lib_name: str) -> bool:
    """检查GUI库是否可用 - 小沈 2026-05-17

    Args:
        lib_name: 库名，如 "pyautogui", "win32gui", "mss"

    Returns:
        bool: 库是否可用
    """
    try:
        importlib.import_module(lib_name)
        return True
    except ImportError:
        return False


def _gui_safe_call(
    lib_name: str,
    error_msg: str,
    func: Callable,
    *args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    """统一GUI安全调用包装 - 小沈 2026-05-17

    先检查库是否可用，可用则调用func，不可用则返回错误。

    Args:
        lib_name: 依赖的库名
        error_msg: 库不可用时的错误消息
        func: 实际调用的函数
        *args, **kwargs: 传给func的参数

    Returns:
        Dict[str, Any]: 统一返回格式
    """
    if not _require_gui_lib(lib_name):
        return {"code": f"ERR_NO_{lib_name.upper()}", "data": None, "message": error_msg}
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return {"code": ERR_GUI_CALL, "data": None, "message": f"调用失败: {str(e)}"}


# ========== 依赖库可用性检测 ==========

try:
    import pyautogui as _pyautogui_mod
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    _pyautogui_mod = None
    PYAUTOGUI_AVAILABLE = False

try:
    import win32api as _win32api_mod
    import win32con as _win32con_mod
    import win32gui as _win32gui_mod
    WIN32_AVAILABLE = True
except ImportError:
    _win32api_mod = None
    _win32con_mod = None
    _win32gui_mod = None
    WIN32_AVAILABLE = False


# ========== 辅助函数 ==========

def _get_mouse_position() -> Dict[str, Any]:
    """获取当前鼠标位置 - 小沈 2026-05-17

    迁移自 gui_helpers.get_mouse_position
    """
    if WIN32_AVAILABLE:
        try:
            point = _win32api_mod.GetCursorPos()
            return create_tool_result(data={"x": point[0], "y": point[1]}, message=f"鼠标位置: ({point[0]}, {point[1]})")
        except Exception as e:
            return {"code": ERR_DESKTOP_GET_MOUSE_POSITION, "data": None, "message": f"获取失败: {str(e)}"}

    if PYAUTOGUI_AVAILABLE:
        try:
            x, y = _pyautogui_mod.position()
            return create_tool_result(data={"x": x, "y": y}, message=f"鼠标位置: ({x}, {y})")
        except Exception as e:
            return {"code": ERR_DESKTOP_GET_MOUSE_POSITION, "data": None, "message": f"获取失败: {str(e)}"}

    return {"code": ERR_DESKTOP_NO_DEPENDENCY, "data": None, "message": "无依赖库可用(win32api/pyautogui均未安装)，无法获取鼠标位置"}


def _check_screen_size() -> Dict[str, Any]:
    """检查屏幕分辨率 - 小沈 2026-05-17

    迁移自 gui_helpers.check_screen_size
    """
    if WIN32_AVAILABLE:
        try:
            width = _win32api_mod.GetSystemMetrics(_win32con_mod.SM_CXSCREEN)
            height = _win32api_mod.GetSystemMetrics(_win32con_mod.SM_CYSCREEN)
            return create_tool_result(data={"width": width, "height": height}, message=f"屏幕分辨率: {width}x{height}")
        except Exception as e:
            return {"code": ERR_DESKTOP_CHECK_SCREEN_SIZE, "data": None, "message": f"获取失败: {str(e)}"}

    if PYAUTOGUI_AVAILABLE:
        try:
            size = _pyautogui_mod.size()
            return create_tool_result(data={"width": size.width, "height": size.height}, message=f"屏幕分辨率: {size.width}x{size.height}")
        except Exception as e:
            return {"code": ERR_DESKTOP_CHECK_SCREEN_SIZE, "data": None, "message": f"获取失败: {str(e)}"}

    return {"code": ERR_DESKTOP_NO_DEPENDENCY, "data": None, "message": "无依赖库可用(win32api/pyautogui均未安装)，无法获取屏幕分辨率"}


def _check_window_exists(window_title: str) -> Dict[str, Any]:
    """检查窗口是否存在 - 小沈 2026-05-17

    迁移自 gui_helpers.check_window_exists，使用 find_windows_by_title 去重
    """
    if not WIN32_AVAILABLE:
        return {"code": ERR_DESKTOP_CHECK_WINDOW, "data": None, "message": "win32库未安装"}

    try:
        hwnds = find_windows_by_title(window_title)
        exists = len(hwnds) > 0
        return create_tool_result(data={"exists": exists}, message=f"窗口 '{window_title}' {'存在' if exists else '不存在'}")
    except Exception as e:
        return {"code": ERR_DESKTOP_CHECK_WINDOW, "data": None, "message": f"检查失败: {str(e)}"}


def _get_window_position(window_title: str) -> Dict[str, Any]:
    """获取窗口位置和大小 - 小沈 2026-05-17

    迁移自 gui_helpers.get_window_position，使用 find_windows_by_title 去重
    """
    if not WIN32_AVAILABLE:
        return {"code": ERR_DESKTOP_GET_WINDOW_POSITION, "data": None, "message": "win32库未安装"}

    try:
        hwnds = find_windows_by_title(window_title)
        if not hwnds:
            return {"code": ERR_DESKTOP_GET_WINDOW_POSITION, "data": None, "message": f"窗口 '{window_title}' 未找到"}

        hwnd = hwnds[0]
        rect = _win32gui_mod.GetWindowRect(hwnd)
        result = {
            "x": rect[0],
            "y": rect[1],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1],
        }
        return create_tool_result(data=result, message=f"窗口位置: ({result['x']}, {result['y']}) 大小: {result['width']}x{result['height']}")
    except Exception as e:
        return {"code": ERR_DESKTOP_GET_WINDOW_POSITION, "data": None, "message": f"获取失败: {str(e)}"}


def _check_capture_permission() -> Dict[str, Any]:
    """检查屏幕捕获权限 - 小沈 2026-05-17

    迁移自 gui_helpers.check_screen_capture_permission
    """
    try:
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        hdc = user32.GetDC(0)
        if hdc:
            user32.ReleaseDC(0, hdc)
            return create_tool_result(data={"has_permission": True}, message="Windows系统默认允许屏幕捕获，已验证可获取桌面DC")
        return create_tool_result(data={"has_permission": False}, message="无法获取桌面DC，屏幕捕获可能受限")
    except Exception as e:
        return {"code": ERR_FILE_CHECK_PERMISSION, "data": None, "message": f"检查屏幕捕获权限失败: {str(e)}"}


def _check_tesseract_available() -> Dict[str, Any]:
    """检查 Tesseract OCR 引擎是否可用 - 小沈 2026-05-17

    迁移自 gui_helpers.check_tesseract_available
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
            return create_tool_result(data={"is_available": True}, message="Tesseract OCR 引擎可用")
        return create_tool_result(data={"is_available": False}, message="Tesseract 命令执行失败")
    except FileNotFoundError:
        return create_tool_result(data={"is_available": False}, message="Tesseract OCR 未安装")
    except Exception as e:
        return {"code": ERR_DESKTOP_CHECK_TESSERACT, "data": None, "message": f"检查失败: {str(e)}"}


def _check_notification_permission() -> Dict[str, Any]:
    """检查系统通知权限 - 小沈 2026-05-17

    迁移自 gui_helpers.check_notification_permission
    """
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "ToastEnabled")
            winreg.CloseKey(key)
            has_permission = bool(value)
            return create_tool_result(data={"has_permission": has_permission}, message=f"通知权限(注册表检查): {'允许' if has_permission else '禁止'}")
        except FileNotFoundError:
            return create_tool_result(data={"has_permission": True}, message="通知权限: 注册表项未找到，Windows系统默认允许")
    except Exception as e:
        return {"code": ERR_FILE_CHECK_PERMISSION, "data": None, "message": f"检查通知权限失败: {str(e)}"}
from app.constants import (
    ERR_DESKTOP_CHECK_SCREEN_SIZE,
    ERR_DESKTOP_CHECK_TESSERACT,
    ERR_DESKTOP_CHECK_WINDOW,
    ERR_DESKTOP_GET_MOUSE_POSITION,
    ERR_DESKTOP_GET_WINDOW_POSITION,
    ERR_DESKTOP_NO_DEPENDENCY,
    ERR_FILE_CHECK_PERMISSION,
    ERR_GUI_CALL,
)
