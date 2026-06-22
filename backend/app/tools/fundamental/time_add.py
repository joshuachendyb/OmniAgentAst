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
from typing import Dict, Any, Optional, Union, Literal

from app.tools.tool_fc_helper import parse_datetime_any as _parse_datetime_any
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_TIME_ADD


def _build_time_add_llm_data(exec_code: str, duration_ms: int, result_time: str, unit: str, delta: float) -> dict:
    """time_add的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"时间加减失败: {delta} {unit}",
            "action": {"tool": "time_add", "tool_zh": "时间加减", "target": str(delta), "params": {"delta": delta, "unit": unit}},
            "status": {"exec_code": "error", "message": "时间加减失败", "code": ERR_TIME_ADD, "detail": "", "hint": "请检查参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"{delta} {unit}后: {result_time}",
        "action": {"tool": "time_add", "tool_zh": "时间加减", "target": str(delta), "params": {"delta": delta, "unit": unit}},
        "status": {"exec_code": "success", "message": "时间加减成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def time_add(delta: float, start: Optional[Union[int, float, str]] = None, unit: Literal["days", "hours", "minutes", "seconds", "months"] = "days") -> Dict[str, Any]:
    """时间加减计算 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        if start is None:
            start_dt = datetime.now().astimezone()
        else:
            start_dt = _parse_datetime_any(start)
            if start_dt is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_time_add_llm_data("error", duration_ms, "", unit, delta)
                return build_error(data={"error_detail": f"无法解析基准时间: {start}", "params": {"start": str(start), "delta": delta, "unit": unit}}, llm_data=llm_data)

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
                new_dt = start_dt + relativedelta(months=int(delta))
            except ImportError:
                new_dt = start_dt + timedelta(days=delta * 30)
        else:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_time_add_llm_data("error", duration_ms, "", unit, delta)
            return build_error(data={"error_detail": f"不支持的单位: {unit_lower}", "params": {"unit": unit_lower, "delta": delta}}, llm_data=llm_data)

        result_time_str = new_dt.strftime("%Y-%m-%d %H:%M:%S")
        dt_parsed = _parse_datetime_any(result_time_str)
        weekday = dt_parsed.strftime("%A") if dt_parsed else ""
        isoweekday = dt_parsed.isoweekday() if dt_parsed else 0

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {
            "result_time": result_time_str,
            "iso": new_dt.isoformat(),
            "timestamp": int(new_dt.timestamp()),
            "tz": new_dt.strftime("%z").replace(":", ""),
            "unit_used": unit_lower,
            "delta_used": delta,
            "weekday": weekday,
            "isoweekday": isoweekday,
        }
        llm_data = _build_time_add_llm_data("success", duration_ms, result_time_str, unit_lower, delta)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_add_llm_data("error", duration_ms, "", unit, delta)
        return build_error(data={"error_detail": str(e), "params": {"delta": delta, "unit": unit, "start": str(start)}}, llm_data=llm_data)


__all__ = ["time_add"]