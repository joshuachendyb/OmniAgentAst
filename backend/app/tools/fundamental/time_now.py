# -*- coding: utf-8 -*-
"""
time_now — 获取当前系统时间
【2026-06-22 小健】从 time_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import time as _time_mod
from datetime import datetime
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_TIME_NOW


def _build_time_now_llm_data(exec_code: str, duration_ms: int, iso: str, formatted: str, weekday: str, detail: str = "", hint: str = "") -> dict:
    """time_now的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-07-05 加detail/hint参数"""
    if exec_code == "error":
        return {
            "summary": "获取当前时间失败",
            "action": {"tool": "timenow", "tool_zh": "获取时间", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "获取当前时间失败", "code": ERR_TIME_NOW, "detail": detail if detail else "", "hint": hint if hint else "请重试"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"获取当前时间成功:{formatted}，{weekday}，",
        "action": {"tool": "timenow", "tool_zh": "获取时间", "target": "", "params": {}},
        "status": {"exec_code": "success", "message": "获取当前时间成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def timenow() -> Dict[str, Any]:
    """获取当前系统时间 — 小欧 2026-06-17 只保留"now"操作; 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        now = datetime.now().astimezone()
        fmt = "%Y-%m-%d %H:%M:%S"
        formatted = now.strftime(fmt)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_now_llm_data("success", duration_ms, now.isoformat(), formatted, now.strftime("%A"))
        return build_success(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_now_llm_data("error", duration_ms, "", "", "", detail=str(e), hint="系统内部错误，请重试")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["timenow"]