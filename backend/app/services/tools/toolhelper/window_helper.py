# -*- coding: utf-8 -*-
"""
窗口管理公共Helper - 统一窗口查找和状态查询

【创建时间】2026-05-18 小沈
【说明】从 desktop_tools.py 和 gui_tools.py 中提取重复的窗口操作逻辑，
       供 desktop 分类统一调用。不注册到tool_registry，不暴露给LLM。

包含函数：
- find_windows_by_title: 统一窗口模糊查找（替代7处重复实现）
- get_window_rect: 获取窗口位置大小
- get_window_state: 获取窗口状态（maximized/minimized/normal）
- check_win32_platform: 检查Windows平台+pywin32依赖

Author: 小沈 - 2026-05-18
"""

import platform
from typing import Any, Dict, List, Optional

from app.utils.logger import logger


_HAS_WIN32 = False
_win32gui = None
_win32con = None

if platform.system() == "Windows":
    try:
        import win32gui as _win32gui_mod
        import win32con as _win32con_mod
        _win32gui = _win32gui_mod
        _win32con = _win32con_mod
        _HAS_WIN32 = True
    except ImportError:
        _HAS_WIN32 = False
        logger.warning("pywin32未安装，窗口Helper将不可用。请执行: pip install pywin32")


def check_win32_platform() -> Optional[Dict[str, Any]]:
    """检查Windows平台和pywin32依赖是否可用 - 小沈 2026-05-18

    Returns:
        None: 平台可用
        Dict: 错误信息（平台不可用）
    """
    if platform.system() != "Windows":
        return {
            "code": "ERR_DESKTOP_NOT_WINDOWS",
            "data": None,
            "message": "此功能仅支持 Windows 系统"
        }
    if not _HAS_WIN32:
        return {
            "code": "ERR_DESKTOP_NO_PYWIN32",
            "data": None,
            "message": "pywin32库未安装，请先执行: pip install pywin32"
        }
    return None


def get_window_rect(hwnd: int) -> Optional[Dict[str, int]]:
    """获取窗口位置和大小 - 小沈 2026-05-18

    Args:
        hwnd: 窗口句柄

    Returns:
        {"left", "top", "right", "bottom", "width", "height"} 或 None
    """
    if not _win32gui:
        return None
    try:
        rect = _win32gui.GetWindowRect(hwnd)
        return {
            "left": rect[0],
            "top": rect[1],
            "right": rect[2],
            "bottom": rect[3],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1]
        }
    except Exception:
        return None


def get_window_state(hwnd: int) -> str:
    """获取窗口状态 - 小沈 2026-05-18

    Args:
        hwnd: 窗口句柄

    Returns:
        "maximized" / "minimized" / "normal" / "unknown"
    """
    if not _win32gui or not _win32con:
        return "unknown"
    try:
        if not _win32gui.IsWindowVisible(hwnd):
            return "minimized"
        placement = _win32gui.GetWindowPlacement(hwnd)
        if placement[1] == _win32con.SW_SHOWMAXIMIZED:
            return "maximized"
        elif placement[1] == _win32con.SW_SHOWMINIMIZED:
            return "minimized"
        else:
            return "normal"
    except Exception:
        return "unknown"


def find_windows_by_title(window_title: str) -> List[int]:
    """按标题模糊匹配查找窗口句柄列表 - 小沈 2026-05-18

    统一窗口查找函数，替代 desktop_tools + gui_tools + gui_helpers 中的7处重复实现。

    Args:
        window_title: 窗口标题（模糊匹配，不区分大小写）

    Returns:
        匹配的窗口句柄列表
    """
    if not _win32gui:
        return []

    windows = []

    def callback(hwnd: int, _: List) -> bool:
        try:
            title = _win32gui.GetWindowText(hwnd)
            if title and window_title.lower() in title.lower():
                windows.append(hwnd)
        except Exception:
            pass
        return True

    _win32gui.EnumWindows(callback, [])
    return windows


def enum_visible_windows() -> List[Dict[str, Any]]:
    """枚举所有可见窗口 - 小沈 2026-05-18

    Returns:
        [{"hwnd", "title", "state", "position"}, ...]
    """
    if not _win32gui:
        return []

    windows = []

    def callback(hwnd: int, _: List) -> bool:
        try:
            if not _win32gui.IsWindowVisible(hwnd):
                return True
            title = _win32gui.GetWindowText(hwnd)
            if not title:
                return True
            rect = get_window_rect(hwnd)
            state = get_window_state(hwnd)
            windows.append({
                "hwnd": hwnd,
                "title": title,
                "state": state,
                "position": rect
            })
        except Exception:
            pass
        return True

    _win32gui.EnumWindows(callback, [])
    return windows


__all__ = [
    "check_win32_platform",
    "get_window_rect",
    "get_window_state",
    "find_windows_by_title",
    "enum_visible_windows",
    "_HAS_WIN32",
    "_win32gui",
    "_win32con",
]
