# -*- coding: utf-8 -*-
"""
mouse_move — 移动鼠标到指定位置
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""

import importlib
import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_DESKTOP_MOUSE_MOVE


def _check_pyautogui() -> bool:
    try:
        importlib.import_module("pyautogui")
        return True
    except ImportError:
        return False


def _build_mouse_move_llm_data(exec_code: str, duration_ms: int, x: int, y: int,
                                err_code: str = "", detail: str = "") -> dict:
    """mouse_move的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"鼠标移动失败: ({x},{y})",
            "action": {"tool": "mouse_move", "tool_zh": "鼠标移动", "target": f"({x},{y})", "params": {"x": x, "y": y}},
            "status": {"exec_code": "error", "message": "鼠标移动失败", "code": err_code or ERR_DESKTOP_MOUSE_MOVE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"鼠标移动到: ({x}, {y})",
        "action": {"tool": "mouse_move", "tool_zh": "鼠标移动", "target": f"({x},{y})", "params": {"x": x, "y": y}},
        "status": {"exec_code": "success", "message": "鼠标移动完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def mouse_move(x: int, y: int) -> Dict[str, Any]:
    """移动鼠标到指定位置 — 小健 2026-06-22 拆分独立文件"""
    duration = 0
    if not _check_pyautogui():
        return build_error(data={"error_detail": "pyautogui库未安装", "params": {}}, llm_data=_build_mouse_move_llm_data("error", 0, x, y, "ERR_NO_PYAUTOGUI"))
    t0 = _time_mod.perf_counter()
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=duration)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"x": x, "y": y}
        llm_data = _build_mouse_move_llm_data("success", duration_ms, x, y)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_mouse_move_llm_data("error", duration_ms, x, y, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {}}, llm_data=llm_data)


__all__ = ["mouse_move"]