# -*- coding: utf-8 -*-
"""
GUI Helper - GUI内部辅助函数集合(不暴露给LLM)
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【创建时间】2026-05-17 小沈
【设计依据】按工具精简方案13.6节,将gui_helpers的7个检查函数迁移到此

【分层规范 - 小健 2026-05-27】
本文件属于【工具层helper】,使用 _response.py 的 build_success/build_error/build_warning
禁止使用 agent/tool_result_utils.py 的 create_xxx 函数

【helper改造原则 - 小健 2026-06-21】
helper是纯数据层,只负责签名兼容(build_success/build_error新签名),不构建llm_data。
llm_data由主工具的builder函数负责,helper不重复构建(DRY原则)。

包含:
- _require_gui_lib(lib_name): 检查GUI库是否可用
- _gui_safe_call(lib_name, error_msg, func, *args, **kwargs): 统一GUI安全调用包装
- _get_mouse_position(): 获取鼠标位置
- _check_screen_size(): 检查屏幕尺寸
- _check_window_exists(window_title): 检查窗口是否存在
- _get_window_position(window_title): 获取窗口位置
- _check_capture_permission(): 检查截屏权限
- _check_tesseract_available(): 检查OCR引擎
- _check_notification_permission(): 检查通知权限
- find_windows_by_title(title): 按标题查找窗口(从window_helper导入)

Author: 小沈 - 2026-05-17
"""

import ctypes
import importlib
import subprocess
from typing import Any, Callable, Dict, List, Optional

from app.tools.tool_response import build_success, build_error
from app.utils.logger import logger
from app.tools.toolhelper.window_helper import find_windows_by_title
from app.tools.tool_constants import SUBPROCESS_TIMEOUT_SHORT


def _require_gui_lib(lib_name: str) -> bool:
    """检查GUI库是否可用 - 小沈 2026-05-17"""
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
    """统一GUI安全调用包装 - 小沈 2026-05-17"""
    if not _require_gui_lib(lib_name):
        return build_error(data={"error": error_msg})
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return build_error(data={"error": f"调用失败: {str(e)}"})


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

def _try_win32_or_pyautogui(win32_func, pyautogui_func, no_dep_msg):
    """WIN32优先→PYAUTOGUI回退的统一双路调用 — 小健 2026-06-17"""
    if WIN32_AVAILABLE:
        try:
            return win32_func()
        except Exception as e:
            return build_error(data={"error": f"获取失败: {str(e)}"})

    if PYAUTOGUI_AVAILABLE:
        try:
            return pyautogui_func()
        except Exception as e:
            return build_error(data={"error": f"获取失败: {str(e)}"})

    return build_error(data={"error": no_dep_msg})


def _get_mouse_position() -> Dict[str, Any]:
    """获取当前鼠标位置 - 小沈 2026-05-17"""
    return _try_win32_or_pyautogui(
        lambda: build_success(data={"x": (p := _win32api_mod.GetCursorPos())[0], "y": p[1]}),
        lambda: build_success(data={"x": (pos := _pyautogui_mod.position())[0], "y": pos[1]}),
        "无依赖库可用(win32api/pyautogui均未安装),无法获取鼠标位置",
    )


def _check_screen_size() -> Dict[str, Any]:
    """检查屏幕分辨率 - 小沈 2026-05-17"""
    return _try_win32_or_pyautogui(
        lambda: build_success(data={"width": (w := _win32api_mod.GetSystemMetrics(_win32con_mod.SM_CXSCREEN)), "height": _win32api_mod.GetSystemMetrics(_win32con_mod.SM_CYSCREEN)}),
        lambda: build_success(data={"width": (s := _pyautogui_mod.size()).width, "height": s.height}),
        "无依赖库可用(win32api/pyautogui均未安装),无法获取屏幕分辨率",
    )


def _check_window_exists(window_title: str) -> Dict[str, Any]:
    """检查窗口是否存在 - 小沈 2026-05-17"""
    if not WIN32_AVAILABLE:
        return build_error(data={"error": "win32库未安装"})

    try:
        hwnds = find_windows_by_title(window_title)
        exists = len(hwnds) > 0
        return build_success(data={"exists": exists})
    except Exception as e:
        return build_error(data={"error": f"检查失败: {str(e)}"})


def _get_window_position(window_title: str) -> Dict[str, Any]:
    """获取窗口位置和大小 - 小沈 2026-05-17"""
    if not WIN32_AVAILABLE:
        return build_error(data={"error": "win32库未安装"})

    try:
        hwnds = find_windows_by_title(window_title)
        if not hwnds:
            return build_error(data={"error": f"窗口 '{window_title}' 未找到"})

        hwnd = hwnds[0]
        rect = _win32gui_mod.GetWindowRect(hwnd)
        result = {
            "x": rect[0],
            "y": rect[1],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1],
        }
        return build_success(data=result)
    except Exception as e:
        return build_error(data={"error": f"获取失败: {str(e)}"})


def _check_capture_permission() -> Dict[str, Any]:
    """检查屏幕捕获权限 - 小沈 2026-05-17"""
    try:
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        hdc = user32.GetDC(0)
        if hdc:
            user32.ReleaseDC(0, hdc)
            return build_success(data={"has_permission": True})
        return build_success(data={"has_permission": False})
    except Exception as e:
        return build_error(data={"error": f"检查屏幕捕获权限失败: {str(e)}"})


def _check_tesseract_available() -> Dict[str, Any]:
    """检查 Tesseract OCR 引擎是否可用 - 小沈 2026-05-17"""
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SHORT,
        )
        available = result.returncode == 0
        return build_success(data={"is_available": available})
    except FileNotFoundError:
        return build_success(data={"is_available": False})
    except Exception as e:
        return build_error(data={"error": f"检查失败: {str(e)}"})


def _check_notification_permission() -> Dict[str, Any]:
    """检查系统通知权限 - 小沈 2026-05-17"""
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "ToastEnabled")
            winreg.CloseKey(key)
            has_permission = bool(value)
            return build_success(data={"has_permission": has_permission})
        except FileNotFoundError:
            return build_success(data={"has_permission": True})
    except Exception as e:
        return build_error(data={"error": f"检查通知权限失败: {str(e)}"})
