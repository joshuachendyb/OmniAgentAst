# -*- coding: utf-8 -*-
"""
window_resize — 调整窗口大小
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""

import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_WINDOW_NOT_FOUND, ERR_WINDOW_RESIZE


def _build_window_resize_llm_data(exec_code: str, duration_ms: int, title: str = "", width: int = 0, height: int = 0,
                                   err_code: str = "", detail: str = "") -> dict:
    """window_resize的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"调整窗口大小失败: {title}",
            "action": {"tool": "window_resize", "tool_zh": "窗口调整", "target": title, "params": {}},
            "status": {"exec_code": "error", "message": "调整窗口大小失败", "code": err_code or ERR_WINDOW_RESIZE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"窗口大小调整完成: {width}x{height}",
        "action": {"tool": "window_resize", "tool_zh": "窗口调整", "target": title, "params": {"width": width, "height": height}},
        "status": {"exec_code": "success", "message": "窗口大小调整完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def window_resize(window_title: str, width: int = 800, height: int = 600) -> Dict[str, Any]:
    """调整窗口大小 — 小健 2026-06-22 拆分独立文件"""
    try:
        import win32gui
    except ImportError:
        return build_error(data={"error_detail": "需要安装 pywin32 库", "params": {"window_title": window_title}}, llm_data=_build_window_resize_llm_data("error", 0, window_title, err_code="ERR_NO_WIN32GUI"))
    t0 = _time_mod.perf_counter()
    try:
        target_hwnd = None
        def _enum_cb(hwnd, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(hwnd):
                win_title = win32gui.GetWindowText(hwnd)
                if window_title.lower() in win_title.lower():
                    target_hwnd = hwnd
            return True
        win32gui.EnumWindows(_enum_cb, None)

        if not target_hwnd:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_window_resize_llm_data("error", duration_ms, window_title, err_code=ERR_WINDOW_NOT_FOUND)
            return build_error(data={"error_detail": f"未找到窗口: {window_title}", "params": {"window_title": window_title}}, llm_data=llm_data)

        left, top, right, bottom = win32gui.GetWindowRect(target_hwnd)
        curr_width = right - left
        curr_height = bottom - top
        new_width = width if width else curr_width
        new_height = height if height else curr_height

        win32gui.MoveWindow(target_hwnd, left, top, new_width, new_height, True)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"title": window_title, "width": new_width, "height": new_height}
        llm_data = _build_window_resize_llm_data("success", duration_ms, window_title, new_width, new_height)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_window_resize_llm_data("error", duration_ms, window_title, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"window_title": window_title}}, llm_data=llm_data)


__all__ = ["window_resize"]