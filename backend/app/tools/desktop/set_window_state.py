# -*- coding: utf-8 -*-
"""
set_window_state — 窗口状态操作(maximize/minimize/restore/topmost/unpin)
【2026-06-22 小健】从window_info.py拆出为独立文件
"""

import time as _time_mod
from typing import Any, Dict, List, Optional

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_INVALID_ACTION, ERR_WINDOW_NOT_FOUND, ERR_WINDOW_SET_STATE, ERR_DESKTOP_GET_WINDOW_INFO
from app.tools.desktop.window_info import (
    check_win32_platform, find_windows_by_title, _win32gui, _win32con,
)


_WINDOW_ACTIONS = {
    "maximize": (_win32gui.ShowWindow, (_win32con.SW_MAXIMIZE,), "已最大化窗口") if _win32gui else None,
    "minimize": (_win32gui.ShowWindow, (_win32con.SW_MINIMIZE,), "已最小化窗口") if _win32gui else None,
    "restore": (_win32gui.ShowWindow, (_win32con.SW_RESTORE,), "已还原窗口") if _win32gui else None,
    "topmost": (_win32gui.SetWindowPos, (_win32con.HWND_TOPMOST, 0, 0, 0, 0,
              _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE), "已置顶窗口") if _win32gui else None,
    "unpin": (_win32gui.SetWindowPos, (_win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
            _win32con.SWP_NOMOVE | _win32con.SWP_NOSIZE), "已取消置顶窗口") if _win32gui else None,
}


def _build_set_window_state_llm_data(exec_code: str, duration_ms: int, action: str, window_title: str = "",
                                      matched_count: int = 0, err_code: str = "", detail: str = "") -> dict:
    """set_window_state的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"窗口操作{action}失败: {window_title}",
            "action": {"tool": "set_window_state", "tool_zh": "窗口状态", "target": window_title, "params": {"action": action}},
            "status": {"exec_code": "error", "message": f"窗口操作{action}失败", "code": err_code or ERR_WINDOW_SET_STATE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    summary = f"窗口操作{action}完成: {window_title}"
    metrics = {}
    if matched_count > 1:
        summary += f"(匹配{matched_count}个窗口)"
        metrics["matched"] = {"value": matched_count, "text": f"{matched_count}个"}
    return {
        "summary": summary,
        "action": {"tool": "set_window_state", "tool_zh": "窗口状态", "target": window_title, "params": {"action": action}},
        "status": {"exec_code": "success", "message": f"窗口操作{action}成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": metrics,
    }


def set_window_state(window_title: str, action: str) -> Dict[str, Any]:
    """设置窗口状态 — 小健 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    err = check_win32_platform()
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_set_window_state_llm_data("error", duration_ms, action, window_title, err_code=ERR_DESKTOP_GET_WINDOW_INFO)
        return build_error(data={"error_detail": "桌面工具不可用", "params": {}}, llm_data=llm_data)

    try:
        if action not in _WINDOW_ACTIONS or _WINDOW_ACTIONS[action] is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_set_window_state_llm_data("error", duration_ms, action, window_title, err_code=ERR_INVALID_ACTION)
            return build_error(data={"error_detail": f"无效的操作: {action}", "params": {"action": action}}, llm_data=llm_data)

        matched_hwnds = find_windows_by_title(window_title)

        if not matched_hwnds:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_set_window_state_llm_data("error", duration_ms, action, window_title, err_code=ERR_WINDOW_NOT_FOUND)
            return build_error(data={"error_detail": f"未找到窗口: {window_title}", "params": {"window_title": window_title}}, llm_data=llm_data)

        hwnd = matched_hwnds[0]
        title = _win32gui.GetWindowText(hwnd)

        func, args, msg_fmt = _WINDOW_ACTIONS[action]
        func(hwnd, *args)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"window_title": title, "action": action, "hwnd": hwnd, "matched_count": len(matched_hwnds)}
        llm_data = _build_set_window_state_llm_data("success", duration_ms, action, title, len(matched_hwnds))
        return build_success(data=data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"set_window_state error: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_set_window_state_llm_data("error", duration_ms, action, window_title, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {}}, llm_data=llm_data)


__all__ = ["set_window_state"]