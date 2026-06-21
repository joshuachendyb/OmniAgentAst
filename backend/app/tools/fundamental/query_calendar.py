# -*- coding: utf-8 -*-
"""
query_calendar — 节日/日期查询
【2026-06-22 小健】从 time_tools.py 拆分为独立文件
"""

import time as _time_mod
from datetime import datetime
from typing import Dict, Any, Optional, Union, Literal

from app.tools.toolhelper.date_helper import (
    parse_datetime_any as _parse_datetime_any,
    is_holiday as _is_holiday,
    calc_next_n_workday as _calc_next_n_workday,
    get_holiday_date_by_name as _get_holiday_date_by_name,
)
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_TIME_DATE


def _build_query_calendar_llm_data(exec_code: str, duration_ms: int, date_str: str, is_weekend: bool, is_hol: bool, is_workday: bool, holiday_name: str) -> dict:
    """query_calendar的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "日期检查失败",
            "action": {"tool": "query_calendar", "tool_zh": "日历查询", "target": date_str, "params": {}},
            "status": {"exec_code": "error", "message": "日期检查失败", "code": ERR_TIME_DATE, "detail": "", "hint": "请检查日期格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    hol_str = f"，{holiday_name}" if holiday_name else ""
    return {
        "summary": f"{date_str}: {'周末' if is_weekend else '工作日' if is_workday else '节假日'}{hol_str}",
        "action": {"tool": "query_calendar", "tool_zh": "日历查询", "target": date_str, "params": {}},
        "status": {"exec_code": "success", "message": "日期检查完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def query_calendar(
    date: Optional[Union[int, float, str]] = None,
    check_type: Literal["weekend", "holiday", "workday", "next_workday"] = "workday",
    n: int = 1,
    name: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """日期综合检查 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        if name:
            holiday_info = _get_holiday_date_by_name(name, year)
            if holiday_info is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_query_calendar_llm_data("error", duration_ms, "", False, False, False, "")
                return build_error(data={"error_detail": f"未找到节日名称: {name}", "params": {"name": name, "year": year}}, llm_data=llm_data)
            date_obj = datetime.strptime(holiday_info["date"], "%Y-%m-%d").date()
            isoweekday = holiday_info["isoweekday"]
            is_weekend = isoweekday >= 6
            is_hol, _ = _is_holiday(date_obj)
            is_workday = not is_weekend and not is_hol
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = {
                "date": holiday_info["date"],
                "weekday": holiday_info["weekday"],
                "isoweekday": isoweekday,
                "is_weekend": is_weekend,
                "is_holiday": is_hol,
                "holiday_name": holiday_info["name"],
                "is_workday": is_workday,
                "holiday_type": holiday_info["type"],
                "matched_by_name": name,
            }
            llm_data = _build_query_calendar_llm_data("success", duration_ms, holiday_info["date"], is_weekend, is_hol, is_workday, holiday_info["name"])
            return build_success(data=data, llm_data=llm_data)

        dt = _parse_datetime_any(date) if date else datetime.now().astimezone()
        if dt is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_calendar_llm_data("error", duration_ms, str(date), False, False, False, "")
            return build_error(data={"error_detail": f"无法解析日期: {date}", "params": {"date": str(date)}}, llm_data=llm_data)

        date_obj = dt.date()
        isoweekday = dt.isoweekday()
        is_weekend = isoweekday >= 6
        is_hol, holiday_name = _is_holiday(date_obj)
        is_workday = not is_weekend and not is_hol

        result_data = {
            "date": date_obj.isoformat(),
            "weekday": dt.strftime("%A"),
            "isoweekday": isoweekday,
            "is_weekend": is_weekend,
            "is_holiday": is_hol,
            "holiday_name": holiday_name,
            "is_workday": is_workday,
        }

        if check_type == "next_workday":
            next_workdays = _calc_next_n_workday(date_obj, n)
            result_data["next_workdays"] = next_workdays
            result_data["next_workday_first"] = next_workdays[0] if next_workdays else None
        elif check_type not in ("weekend", "holiday", "workday"):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_calendar_llm_data("error", duration_ms, str(date), False, False, False, "")
            return build_error(data={"error_detail": f"不支持的check_type: {check_type}", "params": {"check_type": check_type}}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_calendar_llm_data("success", duration_ms, date_obj.isoformat(), is_weekend, is_hol, is_workday, holiday_name or "")
        return build_success(data=result_data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_calendar_llm_data("error", duration_ms, str(date), False, False, False, "")
        return build_error(data={"error_detail": str(e), "params": {"date": str(date), "check_type": check_type}}, llm_data=llm_data)


__all__ = ["query_calendar"]