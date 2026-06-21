# -*- coding: utf-8 -*-
"""
时间工具函数模块 - 为普通用户提供时间相关功能
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【迁移说明】2026-04-26 小沈
- 本文件从 app/tools/time_tools.py 迁移而来

【2026-05-02 小沈重构】
- 移除所有 @register_tool 装饰器,注册由 time_register.py 显式完成
- 移除 register_tool/ToolCategory 导入
- 移除 Pydantic 模型导入(模型由 time_register.py 导入)

【2026-05-18 小沈重构】16→7精简
- 16个公开函数改为内部函数(加下划线前缀)
- 公开函数:time_now, time_add, time_diff, query_calendar, timezone_convert, timer(共7个,后续精简到5个)

【2026-06-12 小沈精简】7→5精简
- 删除timezone_convert(国内用户几乎不用,YAGNI)
- 公开工具: time_now, time_add, time_diff, query_calendar, timer
【2026-06-17 小欧拆分】time_now只保留"now"获取当前时间功能
- 删除format/to_timestamp/from_timestamp三种操作
- 删除_time_format/_time_to_timestamp/_timestamp_to_time内部函数

【2026-06-21 小健】Phase 1 builder改造: build_success/error适配新3字段签名

包含(重构后4个公开工具):
- time_now: 获取当前时间(只保留now操作)
- time_add: 时间加减(增强:months用relativedelta + weekday/isoweekday)
- time_diff: 时间差值(增强:is_after/is_before/is_equal/diff_seconds_signed)
- query_calendar: 日期综合检查(check_type=weekend/holiday/workday/next_workday)

Author: 小沈 - 2026-04-25;
创建时间: 2026-04-25 15:44:54;
更新时间: 2026-06-21;
"""

import time as _time_mod
import json;
from datetime import datetime, timedelta, timezone;
from typing import Dict, Any, Optional, Callable, Awaitable, List, Union, Literal;
import re;
from app.utils.common_patterns import UTC_OFFSET_PATTERN
from app.utils.logger import logger;
from app.utils.time_utils import get_timestamp_ms
from app.utils.tool_result_formatter import truncate_data_for_frontend;
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import HTTPX_TIMEOUT_DEFAULT
from app.tools.toolhelper.date_helper import (
    parse_datetime_any as _parse_datetime_any,
    parse_datetime_string as _parse_datetime_string,
    is_holiday as _is_holiday,
    calc_next_n_workday as _calc_next_n_workday,
    resolve_timezone as _resolve_timezone,
    get_holiday_date_by_name as _get_holiday_date_by_name,
);
from app.constants import (
    ERR_META_CALENDAR_NEXT_N_WORKDAY,
    ERR_META_INVALID_CHECK_TYPE,
    ERR_META_TIME_FORMAT,
    ERR_TIME_ADD,
    ERR_TIME_DATE,
    ERR_TIME_DIFF,
    ERR_TIME_NOW,
)


def _build_time_now_llm(exec_code: str, duration_ms: int, iso: str, formatted: str, weekday: str) -> dict:
    """time_now的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "获取当前时间失败",
            "action": {"tool": "time_now", "tool_zh": "获取时间", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "获取当前时间失败", "code": ERR_TIME_NOW, "detail": "", "hint": "请重试"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"当前时间 {formatted}，{weekday}",
        "action": {"tool": "time_now", "tool_zh": "获取时间", "target": "", "params": {}},
        "status": {"exec_code": "success", "message": "获取当前时间成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def _build_time_add_llm(exec_code: str, duration_ms: int, result_time: str, unit: str, delta: float) -> dict:
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


def _build_time_diff_llm(exec_code: str, duration_ms: int, humanized: str, seconds: int, days: float, is_future: bool) -> dict:
    """time_diff的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "计算时间差失败",
            "action": {"tool": "time_diff", "tool_zh": "时间差值", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "计算时间差失败", "code": ERR_TIME_DIFF, "detail": "", "hint": "请检查时间格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"时间差: {humanized}（{round(days, 2)}天）",
        "action": {"tool": "time_diff", "tool_zh": "时间差值", "target": "", "params": {}},
        "status": {"exec_code": "success", "message": "计算时间差成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"seconds": {"value": seconds, "text": f"{seconds}秒"}, "days": {"value": round(days, 2), "text": f"{round(days, 2)}天"}},
    }


def _build_query_calendar_llm(exec_code: str, duration_ms: int, date_str: str, is_weekend: bool, is_hol: bool, is_workday: bool, holiday_name: str) -> dict:
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


# ===========================================================
# 公开工具函数 — 小健 2026-06-21 Phase 1 builder改造
# ===========================================================

def time_now() -> Dict[str, Any]:
    """获取当前系统时间 — 小欧 2026-06-17 只保留"now"操作; 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        import pytz
        now = datetime.now().astimezone()
        fmt = "%Y-%m-%d %H:%M:%S"
        formatted = now.strftime(fmt)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {
            "iso": now.isoformat(),
            "timestamp": int(now.timestamp()),
            "format": formatted,
            "timezone": now.strftime("%z").replace(":", ""),
            "weekday": now.strftime("%A"),
            "isoweekday": now.isoweekday(),
        }
        llm_data = _build_time_now_llm("success", duration_ms, now.isoformat(), formatted, now.strftime("%A"))
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_now_llm("error", duration_ms, "", "", "")
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def time_add(delta: float, start: Optional[Union[int, float, str]] = None, unit: Literal["days", "hours", "minutes", "seconds", "months"] = "days") -> Dict[str, Any]:
    """时间加减计算 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if start is None:
            start_dt = datetime.now().astimezone()
        else:
            start_dt = _parse_datetime_any(start)
            if start_dt is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_time_add_llm("error", duration_ms, "", unit, delta)
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
            llm_data = _build_time_add_llm("error", duration_ms, "", unit, delta)
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
        llm_data = _build_time_add_llm("success", duration_ms, result_time_str, unit_lower, delta)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_add_llm("error", duration_ms, "", unit, delta)
        return build_error(data={"error_detail": str(e), "params": {"delta": delta, "unit": unit, "start": str(start)}}, llm_data=llm_data)


def time_diff(start: Union[int, float, str], end: Optional[Union[int, float, str]] = None) -> Dict[str, Any]:
    """计算时间差值 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        start_dt = _parse_datetime_any(start)
        if start_dt is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_time_diff_llm("error", duration_ms, "", 0, 0, False)
            return build_error(data={"error_detail": f"无法解析开始时间: {start}", "params": {"start": str(start)}}, llm_data=llm_data)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()

        if end is None:
            end_dt = datetime.now().astimezone()
        else:
            end_dt = _parse_datetime_any(end)
            if end_dt is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_time_diff_llm("error", duration_ms, "", 0, 0, False)
                return build_error(data={"error_detail": f"无法解析结束时间: {end}", "params": {"end": str(end)}}, llm_data=llm_data)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc).astimezone()

        delta = end_dt - start_dt
        total_seconds = abs(delta.total_seconds())
        now = datetime.now().astimezone()
        is_future = end_dt > now

        seconds = int(total_seconds)
        minutes = total_seconds / 60.0
        hours = total_seconds / 3600.0
        days = total_seconds / 86400.0

        if total_seconds < 60:
            humanized = "刚刚" if not is_future else "即将"
        elif total_seconds < 3600:
            mins = int(total_seconds / 60)
            humanized = f"{mins}分钟前" if not is_future else f"{mins}分钟后"
        elif total_seconds < 86400:
            hrs = int(total_seconds / 3600)
            humanized = f"{hrs}小时前" if not is_future else f"{hrs}小时后"
        elif total_seconds < 2592000:
            d = int(total_seconds / 86400)
            humanized = f"{d}天前" if not is_future else f"{d}天后"
        elif total_seconds < 31104000:
            m = int(total_seconds / 2592000)
            humanized = f"{m}个月前" if not is_future else f"{m}个月后"
        else:
            y = int(total_seconds / 31104000)
            humanized = f"{y}年前" if not is_future else f"{y}年后"

        diff_signed = delta.total_seconds()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {
            "humanized": humanized,
            "seconds": seconds,
            "minutes": minutes,
            "hours": hours,
            "days": days,
            "is_future": is_future,
            "is_after": diff_signed > 0,
            "is_before": diff_signed < 0,
            "is_equal": diff_signed == 0,
            "diff_seconds_signed": diff_signed,
        }
        llm_data = _build_time_diff_llm("success", duration_ms, humanized, seconds, days, is_future)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_diff_llm("error", duration_ms, "", 0, 0, False)
        return build_error(data={"error_detail": str(e), "params": {"start": str(start), "end": str(end)}}, llm_data=llm_data)


def query_calendar(
    date: Optional[Union[int, float, str]] = None,
    check_type: Literal["weekend", "holiday", "workday", "next_workday"] = "workday",
    n: int = 1,
    name: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """日期综合检查 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if name:
            holiday_info = _get_holiday_date_by_name(name, year)
            if holiday_info is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_query_calendar_llm("error", duration_ms, "", False, False, False, "")
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
            llm_data = _build_query_calendar_llm("success", duration_ms, holiday_info["date"], is_weekend, is_hol, is_workday, holiday_info["name"])
            return build_success(data=data, llm_data=llm_data)

        dt = _parse_datetime_any(date) if date else datetime.now().astimezone()
        if dt is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_calendar_llm("error", duration_ms, str(date), False, False, False, "")
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
            llm_data = _build_query_calendar_llm("error", duration_ms, str(date), False, False, False, "")
            return build_error(data={"error_detail": f"不支持的check_type: {check_type}", "params": {"check_type": check_type}}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_calendar_llm("success", duration_ms, date_obj.isoformat(), is_weekend, is_hol, is_workday, holiday_name or "")
        return build_success(data=result_data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_calendar_llm("error", duration_ms, str(date), False, False, False, "")
        return build_error(data={"error_detail": str(e), "params": {"date": str(date), "check_type": check_type}}, llm_data=llm_data)
