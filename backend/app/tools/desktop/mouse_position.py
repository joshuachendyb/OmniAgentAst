# -*- coding: utf-8 -*-
"""
mouse_position — 获取鼠标当前位置
【2026-06-22 小健】从 desktop_tools.py 拆分为独立文件
"""

import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error


def _build_mouse_position_llm_data(exec_code: str, duration_ms: int, x=0, y=0, detail: str = "") -> dict:
    """mouse_position的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"获取鼠标位置失败: {detail}",
            "action": {"tool": "mouse_position", "tool_zh": "获取鼠标位置", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "获取鼠标位置失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"鼠标位置: ({x},{y})",
        "action": {"tool": "mouse_position", "tool_zh": "获取鼠标位置", "target": f"({x},{y})", "params": {"x": x, "y": y}},
        "status": {"exec_code": "success", "message": "获取鼠标位置成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _get_mouse_position() -> Dict[str, Any]:
    """获取当前鼠标位置(内聚) — 小健 2026-06-22"""
    try:
        import ctypes
        point = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return build_success(data={"x": point.x, "y": point.y})
    except Exception:
        pass
    try:
        import pyautogui
        pos = pyautogui.position()
        return build_success(data={"x": pos[0], "y": pos[1]})
    except ImportError:
        return build_error(data={"error_detail": "无依赖库可用(win32api/pyautogui均未安装)", "params": {}})
    except Exception as e:
        return build_error(data={"error_detail": str(e), "params": {}})


def mouse_position() -> Dict[str, Any]:
    """获取鼠标当前位置 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    result = _get_mouse_position()
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if result.get("llm_data", {}).get("status", {}).get("exec_code") == "error" or "error_detail" in result.get("data", {}):
        detail = result.get("data", {}).get("error_detail", "获取鼠标位置失败")
        llm_data = _build_mouse_position_llm_data("error", duration_ms, detail=detail)
        return build_error(data=result.get("data", {}), llm_data=llm_data)
    data = result.get("data", {})
    x, y = data.get("x", 0), data.get("y", 0)
    llm_data = _build_mouse_position_llm_data("success", duration_ms, x, y)
    return build_success(data=data, llm_data=llm_data)


__all__ = ["mouse_position"]