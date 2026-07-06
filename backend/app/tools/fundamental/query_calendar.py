# -*- coding: utf-8 -*-
"""
query_calendar — 节日/日期查询
【2026-06-22 小健】从 time_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from datetime import datetime
from typing import Dict, Any, Optional, Union, Literal

from app.tools.tool_fc_helper import (
    parse_datetime_any as _parse_datetime_any,
    is_holiday as _is_holiday,
    calc_next_n_workday as _calc_next_n_workday,
    get_holiday_date_by_name as _get_holiday_date_by_name,
)
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_TIME_DATE

_WEEKDAY_CN = {
    "Monday": "星期一", "Tuesday": "星期二", "Wednesday": "星期三",
    "Thursday": "星期四", "Friday": "星期五", "Saturday": "星期六", "Sunday": "星期日",
}
_HOLIDAY_TYPE_CN = {"lunar": "农历", "solar": "公历", "qingming": "节气"}


def _build_query_calendar_llm_data(exec_code: str, duration_ms: int, date_str: str,
                                    is_weekend: bool, is_hol: bool, is_workday: bool,
                                    holiday_name: str, detail: str = "",
                                    user_name: str = "", user_year: Optional[int] = None,
                                    hint: str = "", weekday_cn: str = "",
                                    holiday_type_cn: str = "") -> dict:
    """query_calendar的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-07-05 加detail/user_name/user_year — 小欧 2026-07-05 加hint参数 — 小欧 2026-07-06 加weekday_cn/holiday_type_cn"""
    act_params = {"name": user_name}
    if user_year is not None:
        act_params["year"] = user_year
    if exec_code == "error":
        return {
            "summary": f"日期检查失败: {user_name}" if user_name else "日期检查失败",
            "action": {"tool": "calendar", "tool_zh": "日历查询", "target": date_str or user_name, "params": act_params},
            "status": {"exec_code": "error", "message": "日期检查失败", "code": ERR_TIME_DATE, "detail": detail, "hint": hint if hint else "请检查日期格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    hol_str = f"，{holiday_name}" if holiday_name else ""
    type_str = f"（{holiday_type_cn}）" if holiday_type_cn else ""
    return {
        "summary": f"{date_str} {weekday_cn}: {'周末' if is_weekend else '工作日' if is_workday else '节假日'}{hol_str}{type_str}",
        "action": {"tool": "calendar", "tool_zh": "日历查询", "target": date_str, "params": act_params},
        "status": {"exec_code": "success", "message": "日期检查完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def calendar(
    name: str,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """节日/日期查询 — 小健 2026-06-22 拆分独立文件 — 小健 2026-06-24 参数简化
    
    name参数支持两种用法：
    - 传节日名（如"端午节"）→ 返回节日日期和信息
    - 传日期字符串（如"2026-06-23"）→ 返回工作日/节假日判断
    """
    t0 = _time_mod.perf_counter()
    try:
        dt = _parse_datetime_any(name)
        if dt is not None:
            date_obj = dt.date()
            isoweekday = dt.isoweekday()
            is_weekend = isoweekday >= 6
            is_hol, holiday_name = _is_holiday(date_obj)
            is_workday = not is_weekend and not is_hol
            
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            weekday_cn = _WEEKDAY_CN.get(dt.strftime("%A"), "")
            llm_data = _build_query_calendar_llm_data("success", duration_ms, date_obj.isoformat(), is_weekend, is_hol, is_workday, holiday_name or "", user_name=name, user_year=year, weekday_cn=weekday_cn)
            return build_success(data={}, llm_data=llm_data)
        
        holiday_info = _get_holiday_date_by_name(name, year)
        if holiday_info is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_calendar_llm_data("error", duration_ms, "", False, False, False, "", detail=f"未找到节日名称或无效日期: {name}", hint="请检查节日名称或日期格式是否正确", user_name=name, user_year=year)
            return build_error(data={"error_detail": f"未找到节日名称或无效日期: {name}", "params": {"name": name, "year": year}}, llm_data=llm_data)
        
        date_obj = datetime.strptime(holiday_info["date"], "%Y-%m-%d").date()
        isoweekday = holiday_info["isoweekday"]
        is_weekend = isoweekday >= 6
        is_hol, _ = _is_holiday(date_obj)
        is_workday = not is_weekend and not is_hol
        weekday_cn = _WEEKDAY_CN.get(holiday_info["weekday"], "")
        holiday_type_cn = _HOLIDAY_TYPE_CN.get(holiday_info["type"], "")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_calendar_llm_data("success", duration_ms, holiday_info["date"], is_weekend, is_hol, is_workday, holiday_info["name"], user_name=name, user_year=year, weekday_cn=weekday_cn, holiday_type_cn=holiday_type_cn)
        return build_success(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_calendar_llm_data("error", duration_ms, str(name), False, False, False, "", detail=str(e), hint="系统内部错误，请重试", user_name=name, user_year=year)
        return build_error(data={"error_detail": str(e), "params": {"name": str(name)}}, llm_data=llm_data)


__all__ = ["calendar"]