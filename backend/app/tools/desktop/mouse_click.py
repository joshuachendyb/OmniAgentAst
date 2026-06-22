# -*- coding: utf-8 -*-
"""
mouse_click — 鼠标单击
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import importlib
import time as _time_mod
from typing import Dict, Any, Optional

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_DESKTOP_MOUSE_CLICK


def _check_pyautogui() -> bool:
    try:
        importlib.import_module("pyautogui")
        return True
    except ImportError:
        return False


def _build_mouse_click_llm_data(exec_code: str, duration_ms: int, x, y, button: str = "", click_type: str = "",
                                 err_code: str = "", detail: str = "") -> dict:
    """mouse_click的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"点击失败: {detail}",
            "action": {"tool": "mouse_click", "tool_zh": "点击", "target": f"({x},{y})", "params": {"x": x, "y": y, "button": button}},
            "status": {"exec_code": "error", "message": f"点击失败: {detail}", "code": err_code or ERR_DESKTOP_MOUSE_CLICK, "detail": detail, "hint": "请检查坐标是否在屏幕范围内"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"点击 ({x},{y})",
        "action": {"tool": "mouse_click", "tool_zh": "点击", "target": f"({x},{y})", "params": {"x": x, "y": y, "button": button, "click_type": click_type}},
        "status": {"exec_code": "success", "message": "点击成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"x": {"value": x, "text": f"X={x}"}, "y": {"value": y, "text": f"Y={y}"}, "button": {"value": button, "text": f"{button}键"}, "click_type": {"value": click_type, "text": f"{click_type}击"}},
    }


def mouse_click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> Dict[str, Any]:
    """鼠标单击 — 小健 2026-06-22 拆分独立文件 — 小健 2026-06-22 修复计时铁规"""
    t0 = _time_mod.perf_counter()
    click_type = "single"
    if not _check_pyautogui():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return build_error(data={"error_detail": "pyautogui库未安装", "params": {}}, llm_data=_build_mouse_click_llm_data("error", duration_ms, x, y, button, click_type, "ERR_NO_PYAUTOGUI"))
    try:
        import pyautogui
        clicks = 2 if click_type == "double" else 1
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {}
        llm_data = _build_mouse_click_llm_data("success", duration_ms, x, y, button, click_type)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_mouse_click_llm_data("error", duration_ms, x, y, button, click_type, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {}}, llm_data=llm_data)


__all__ = ["mouse_click"]