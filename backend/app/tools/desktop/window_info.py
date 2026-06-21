# -*- coding: utf-8 -*-
"""
window_info — 列出所有窗口
【2026-06-22 小健】从 desktop_tools.py 拆分为独立文件
"""

import platform
import time as _time_mod
from typing import Any, Dict, List, Optional

from app.utils.logger import logger
from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_DESKTOP_GET_WINDOW_INFO, ERR_INVALID_ACTION, ERR_WINDOW_LIST, ERR_WINDOW_NOT_FOUND, ERR_WINDOW_SET_STATE


_HAS_WIN32 = False
_win32gui = None
_win32con = None
_win32api = None

if platform.system() == "Windows":
    try:
        import win32gui as _win32gui_mod
        import win32con as _win32con_mod
        import win32api as _win32api_mod

        _win32gui = _win32gui_mod
        _win32con = _win32con_mod
        _win32api = _win32api_mod
        _HAS_WIN32 = True
    except ImportError:
        _HAS_WIN32 = False
        logger.warning("pywin32未安装,桌面工具将不可用。请执行: pip install pywin32")


def check_win32_platform() -> Optional[Dict[str, Any]]:
    """检查Windows平台和pywin32依赖是否可用 — 小健 2026-06-22"""
    if platform.system() != "Windows":
        return build_error(data={"error_detail": "此功能仅支持Windows系统", "params": {}})
    if not _HAS_WIN32:
        return build_error(data={"error_detail": "pywin32库未安装,请先执行: pip install pywin32", "params": {}})
    return None


def get_window_rect(hwnd: int) -> Optional[Dict[str, int]]:
    """获取窗口位置和大小 — 小健 2026-06-22"""
    if not _win32gui:
        return None
    try:
        rect = _win32gui.GetWindowRect(hwnd)
        return {
            "left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3],
            "width": rect[2] - rect[0], "height": rect[3] - rect[1],
        }
    except Exception:
        return None


def get_window_state(hwnd: int) -> str:
    """获取窗口状态 — 小健 2026-06-22"""
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
    """按标题模糊匹配查找窗口句柄列表 — 小健 2026-06-22"""
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


def _enum_windows_callback(hwnd: int, windows: List[Dict]) -> bool:
    """枚举窗口回调函数 — 小健 2026-06-22"""
    try:
        if not _win32gui.IsWindowVisible(hwnd):
            return True
        title = _win32gui.GetWindowText(hwnd)
        if not title:
            return True
        rect = get_window_rect(hwnd)
        state = get_window_state(hwnd)
        windows.append({"hwnd": hwnd, "title": title, "state": state, "position": rect})
    except Exception:
        pass
    return True


_WINDOW_ACTIONS = {
    "maximize": (_win32gui.ShowWindow, (_win32con.SW_MAXIMIZE,), "已最大化窗口") if _HAS_WIN32 else None,
    "minimize": (_win32gui.ShowWindow, (_win32con.SW_MINIMIZE,), "已最小化窗口") if _HAS_WIN32 else None,
    "restore": (_win32gui.ShowWindow, (_win32con.SW_RESTORE,), "已还原窗口") if _HAS_WIN32 else None,
    "topmost": (_win32gui.SetWindowPos, (_win32con.HWND_TOPMOST, 0, 0, 0, 0,
              _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE), "已置顶窗口") if _HAS_WIN32 else None,
    "unpin": (_win32gui.SetWindowPos, (_win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
            _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE), "已取消置顶窗口") if _HAS_WIN32 else None,
}


def _build_window_info_llm_data(exec_code: str, duration_ms: int, window_count: int, filter_title: str = "") -> dict:
    """window_info的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": "获取窗口列表失败",
            "action": {"tool": "window_info", "tool_zh": "窗口信息", "target": filter_title or "全部", "params": {"filter_title": filter_title}},
            "status": {"exec_code": "error", "message": "获取窗口列表失败", "code": ERR_WINDOW_LIST, "detail": "", "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"共找到 {window_count} 个窗口",
        "action": {"tool": "window_info", "tool_zh": "窗口信息", "target": filter_title or "全部", "params": {"filter_title": filter_title}},
        "status": {"exec_code": "success", "message": "获取窗口列表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"windows": {"value": window_count, "text": f"{window_count}个"}},
    }


def window_info(include_minimized: bool = False, filter_title: Optional[str] = None) -> Dict[str, Any]:
    """列出所有窗口 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    err = check_win32_platform()
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_info_llm_data("error", duration_ms, 0, filter_title or "")
        return build_error(data={"error_detail": "桌面工具不可用", "params": {}}, llm_data=llm_data)

    try:
        windows = []
        _win32gui.EnumWindows(_enum_windows_callback, windows)
        if not include_minimized:
            windows = [w for w in windows if w["state"] != "minimized"]
        if filter_title:
            windows = [w for w in windows if filter_title.lower() in w["title"].lower()]

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = truncate_data_for_frontend({"windows": windows, "total": len(windows)})
        llm_data = _build_window_info_llm_data("success", duration_ms, len(windows), filter_title or "")
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        logger.error(f"window_info list error: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_info_llm_data("error", duration_ms, 0, filter_title or "")
        return build_error(data={"error_detail": str(e), "params": {}}, llm_data=llm_data)


__all__ = ["window_info", "check_win32_platform", "get_window_rect", "get_window_state", "find_windows_by_title", "_HAS_WIN32", "_win32gui", "_win32con", "_win32api"]