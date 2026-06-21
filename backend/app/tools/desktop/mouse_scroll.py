# -*- coding: utf-8 -*-
"""
mouse_scroll — 鼠标滚轮滚动
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""

import importlib
import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_DESKTOP_MOUSE_SCROLL


def _check_pyautogui() -> bool:
    try:
        importlib.import_module("pyautogui")
        return True
    except ImportError:
        return False


def _build_mouse_scroll_llm_data(exec_code: str, duration_ms: int, direction: str = "", amount: int = 0,
                                  err_code: str = "", detail: str = "") -> dict:
    """mouse_scroll的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": "鼠标滚动失败",
            "action": {"tool": "mouse_scroll", "tool_zh": "鼠标滚动", "target": "", "params": {"direction": direction, "amount": amount}},
            "status": {"exec_code": "error", "message": "滚动失败", "code": err_code or ERR_DESKTOP_MOUSE_SCROLL, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"滚动完成: {direction} {amount}单位",
        "action": {"tool": "mouse_scroll", "tool_zh": "鼠标滚动", "target": "", "params": {"direction": direction, "amount": amount}},
        "status": {"exec_code": "success", "message": "滚动完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def mouse_scroll(direction: str = "down", amount: int = 3) -> Dict[str, Any]:
    """鼠标滚轮滚动 — 小健 2026-06-22 拆分独立文件"""
    if not _check_pyautogui():
        return build_error(data={"error_detail": "pyautogui库未安装", "params": {}}, llm_data=_build_mouse_scroll_llm_data("error", 0, direction, amount, "ERR_NO_PYAUTOGUI"))
    t0 = _time_mod.perf_counter()
    try:
        import pyautogui
        scroll_amount = -amount if direction == "down" else amount
        pyautogui.scroll(scroll_amount)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"direction": direction, "amount": amount}
        llm_data = _build_mouse_scroll_llm_data("success", duration_ms, direction, amount)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_mouse_scroll_llm_data("error", duration_ms, direction, amount, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {}}, llm_data=llm_data)


__all__ = ["mouse_scroll"]