# -*- coding: utf-8 -*-
"""
mouse_click — 鼠标单击
【2026-06-22 小健】从 desktop_tools.py/desktop_gui_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
# 2026-07-30 - 小欧 - #4:x/y=None时summary显示"当前位置"替代"None"
# 2026-07-30 - 小欧 - 运行时异常hint去掉"或pyautogui库是否可用"(pyautogui已通过检查)
# 2026-07-30 - 小欧 - 删除click_type冗余变量(YAGNI),直接clicks=1+内联"single"
# 2026-07-31 - 小欧 - 三堂会审修复B7:metrics的click_type文本"single击"中英混用,改"单击"
# 2026-07-31 - 小欧 - 三堂会审增强:支持双击,加clicks参数(默认1),click_type按clicks动态生成single/double
# 2026-08-05 - 小欧 - 三堂会审修复#6: button/clicks 无运行时校验(绕过schema Literal直接调函数路径漏), 加 left/right/middle 与 1/2 校验
# 2026-08-05 - 小欧 - 三堂会审复核: success metrics按钮文本"left键"中英混用(B7同类问题), 改左键/右键/中键

import time as _time_mod
from typing import Dict, Any, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.desktop.desktop_register import check_pyautogui_available
from app.tools.tool_constants import ERR_DESKTOP_MOUSE_CLICK
from app.logger import logger


def _build_mouse_click_llm_data(exec_code: str, duration_ms: int, x, y, button: str = "", clicks: int = 1,
                                 err_code: str = "", detail: str = "", hint: str = "") -> dict:
    """mouse_click的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 加hint参数 — 小欧 2026-07-31 加clicks"""
    x_str = str(x) if x is not None else "当前位置"
    y_str = str(y) if y is not None else "当前位置"
    click_type = "double" if clicks == 2 else "single"
    click_type_text = "双击" if clicks == 2 else "单击"
    button_cn = {"left": "左键", "right": "右键", "middle": "中键"}.get(button, button)
    if exec_code == "error":
        return {
            "summary": f"{click_type_text}({x_str},{y_str})，失败: {detail}",
            "action": {"tool": "mouse_click", "tool_zh": "点击", "target": f"({x_str},{y_str})", "params": {"x": x, "y": y, "button": button, "clicks": clicks}},
            "status": {"exec_code": "error", "message": f"点击失败: {detail}", "code": err_code or ERR_DESKTOP_MOUSE_CLICK, "detail": detail, "hint": hint if hint else "请检查坐标是否在屏幕范围内"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"{click_type_text}({x_str},{y_str})，成功",
        "action": {"tool": "mouse_click", "tool_zh": "点击", "target": f"({x_str},{y_str})", "params": {"x": x, "y": y, "button": button, "clicks": clicks}},
        "status": {"exec_code": "success", "message": f"{click_type_text}成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"x": {"value": x, "text": f"X={x_str}"}, "y": {"value": y, "text": f"Y={y_str}"}, "button": {"value": button, "text": button_cn}, "click_type": {"value": click_type, "text": click_type_text}},
    }


def mouse_click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
    """鼠标点击 — 小健 2026-06-22 拆分独立文件 — 小健 2026-06-22 修复计时铁规 — 小欧 2026-07-31 支持双击"""
    t0 = _time_mod.perf_counter()
    # 2026-08-05 小欧 #6: button/clicks 运行时校验(防 LLM 直接调函数路径绕过 schema Literal)
    if button not in ("left", "right", "middle"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_mouse_click_llm_data("error", duration_ms, x, y, button, clicks, detail="button必须为left/right/middle", hint="请提供有效的鼠标按钮:left(左)/right(右)/middle(中)")
        return build_error(data={}, llm_data=llm_data)
    if clicks not in (1, 2):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_mouse_click_llm_data("error", duration_ms, x, y, button, clicks, detail="clicks必须为1或2", hint="请提供有效的点击次数:1(单击)/2(双击)")
        return build_error(data={}, llm_data=llm_data)
    if not check_pyautogui_available():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        logger.error("mouse_click: pyautogui未安装,工具暂时不能使用。请执行: pip install pyautogui")
        return build_error(data={}, llm_data=_build_mouse_click_llm_data("error", duration_ms, x, y, button, clicks, "ERR_NO_PYAUTOGUI", detail="pyautogui库未安装", hint="工具暂时不能使用:需要安装pyautogui库,请执行: pip install pyautogui"))
    try:
        import pyautogui
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {}
        llm_data = _build_mouse_click_llm_data("success", duration_ms, x, y, button, clicks)
        # ---- observation_formatter route -------------------------------------------
        # branch: #0 空data (L73)
        # trigger: data 为 {} → if not data: return ""
        # handler: 直接返回空字符串
        # file:    observation_formatter.py:73-74
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_mouse_click_llm_data("error", duration_ms, x, y, button, clicks, detail=str(e), hint="请检查坐标是否在屏幕范围内")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["mouse_click"]
