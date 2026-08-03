# -*- coding: utf-8 -*-
"""
time_add — 时间加减运算
【2026-06-22 小健】从 time_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Literal

from app.tools.tool_fc_helper import parse_datetime_any as _parse_datetime_any
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_TIME_ADD


def _build_time_add_llm_data(exec_code: str, duration_ms: int, result_time: str, unit: str, delta: float, detail: str = "", hint: str = "", user_start: Optional[str] = None) -> dict:
    """time_add的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-07-05 补start参数 + detail透传 — 小欧 2026-07-05 加hint参数"""
    _act_params = {"delta": delta, "unit": unit}
    if user_start is not None:
        _act_params["start"] = user_start
    if exec_code == "error":
        return {
            "summary": f"时间加减，{delta:+g} {unit}，失败",
            "action": {"tool": "timeadd", "tool_zh": "时间加减", "target": str(delta), "params": _act_params},
            "status": {"exec_code": "error", "message": "时间加减失败", "code": ERR_TIME_ADD, "detail": detail, "hint": hint if hint else "请检查参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"时间加减，{delta:+g} {unit}后为 {result_time}，成功",
        "action": {"tool": "timeadd", "tool_zh": "时间加减", "target": str(delta), "params": _act_params},
        "status": {"exec_code": "success", "message": "时间加减成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def timeadd(delta: float, start: Optional[str] = None, unit: Literal["days", "hours", "minutes", "seconds", "months"] = "days") -> Dict[str, Any]:
    """时间加减计算 — 小健 2026-06-22 拆分独立文件 — 小健 2026-06-26 删除Union，只支持str"""
    t0 = _time_mod.perf_counter()
    try:
        if start is None:
            start_dt = datetime.now().astimezone()
        else:
            start_dt = _parse_datetime_any(start)
            if start_dt is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_time_add_llm_data("error", duration_ms, "", unit, delta, detail=f"无法解析基准时间: {start}", hint="请检查基准时间格式是否正确", user_start=start)
                return build_error(data={}, llm_data=llm_data)

        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()

        unit_lower = unit.lower()
        _DELTA_BUILDERS = {
            "days": timedelta(days=delta),
            "hours": timedelta(hours=delta),
            "minutes": timedelta(minutes=delta),
            "seconds": timedelta(seconds=delta),
        }
        if unit_lower in _DELTA_BUILDERS:
            new_dt = start_dt + _DELTA_BUILDERS[unit_lower]
        elif unit_lower == "months":
            try:
                from dateutil.relativedelta import relativedelta
                whole_months = int(delta)
                frac_days = (delta - whole_months) * 30
                new_dt = start_dt + relativedelta(months=whole_months) + timedelta(days=frac_days)
            except ImportError:
                new_dt = start_dt + timedelta(days=delta * 30)
        else:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_time_add_llm_data("error", duration_ms, "", unit, delta, detail=f"不支持的单位: {unit_lower}", hint="请使用days/hours/minutes/seconds/months作为单位", user_start=start)
            return build_error(data={}, llm_data=llm_data)

        result_time_str = new_dt.strftime("%Y-%m-%d %H:%M:%S")
        dt_parsed = _parse_datetime_any(result_time_str)
        weekday = dt_parsed.strftime("%A") if dt_parsed else ""
        isoweekday = dt_parsed.isoweekday() if dt_parsed else 0

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_add_llm_data("success", duration_ms, result_time_str, unit_lower, delta, user_start=start)
        return build_success(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_add_llm_data("error", duration_ms, "", unit, delta, detail=str(e), hint="系统内部错误，请重试", user_start=start)
        return build_error(data={}, llm_data=llm_data)


__all__ = ["timeadd"]
