# -*- coding: utf-8 -*-
"""
mouse_position — 获取鼠标当前位置
【2026-06-22 小健】从 desktop_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
# 2026-07-30 - 小欧 - #5:if x or y改为if x is not None or y is not None,修复(0,0)被跳过
# 2026-07-30 - 小欧 - error_detail/hint修正:不提win32api/pywin32(实际用ctypes标准库)
# 2026-07-31 - 小欧 - 三堂会审修复B19:补import ctypes.wintypes,原ctypes主路径因未导入该子模块抛AttributeError成为死代码,始终走pyautogui fallback
import ctypes
import ctypes.wintypes
import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_DESKTOP_GET_MOUSE_POSITION
from app.logger import logger


def _build_mouse_position_llm_data(exec_code: str, duration_ms: int, x=0, y=0, detail: str = "", hint: str = "") -> dict:
    """mouse_position的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 修复空error code — 小欧 2026-07-05 加hint参数"""
    _act_params = {}
    if x is not None or y is not None:
        _act_params["x"] = x
        _act_params["y"] = y
    if exec_code == "error":
        return {
            "summary": f"获取鼠标位置失败: {detail}",
            "action": {"tool": "mouse_position", "tool_zh": "获取鼠标位置", "target": "", "params": _act_params},
            "status": {"exec_code": "error", "message": "获取鼠标位置失败", "code": ERR_DESKTOP_GET_MOUSE_POSITION, "detail": detail, "hint": hint if hint else "请检查鼠标设备"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"获取鼠标位置成功: 当前({x},{y})",
        "action": {"tool": "mouse_position", "tool_zh": "获取鼠标位置", "target": f"({x},{y})", "params": _act_params},
        "status": {"exec_code": "success", "message": "获取鼠标位置成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _get_mouse_position() -> Dict[str, Any]:
    """获取当前鼠标位置(内聚) — 小健 2026-06-22 拆分独立文件"""
    try:
        point = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return {"x": point.x, "y": point.y}
    except Exception:
        pass
    try:
        import pyautogui
        pos = pyautogui.position()
        return {"x": pos[0], "y": pos[1]}
    except ImportError:
        logger.error("mouse_position: pyautogui未安装,工具暂时不能使用。请执行: pip install pyautogui")
        return {"error_detail": "无可用依赖(ctypes获取失败,pyautogui未安装)", "params": {"library": "ctypes/pyautogui"}}
    except Exception as e:
        return {"error_detail": str(e), "params": {"library": "ctypes/pyautogui"}}


def mouse_position() -> Dict[str, Any]:
    """获取鼠标当前位置 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    result = _get_mouse_position()
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if "error_detail" in result:
        llm_data = _build_mouse_position_llm_data("error", duration_ms, detail=result["error_detail"], hint="鼠标位置获取不可用,请检查系统环境或安装pyautogui库")
        return build_error(data={}, llm_data=llm_data)
    x, y = result.get("x", 0), result.get("y", 0)
    llm_data = _build_mouse_position_llm_data("success", duration_ms, x, y)
    # ---- observation_formatter route -------------------------------------------
    # branch: #21 fallback (key:val)
    # trigger: 无上述20条分支匹配 — x/y 不命中专用分支
    # handler: _format_scalar_data(data) — key | value 单行列表
    # file:    observation_formatter.py:214
    # ------------------------------------------------------------------------------
    return build_success(data={"x": x, "y": y}, llm_data=llm_data)


__all__ = ["mouse_position"]
