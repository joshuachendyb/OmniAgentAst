# -*- coding: utf-8 -*-
"""
time_diff — 时间差值计算
【2026-06-22 小健】从 time_tools.py 拆分为独立文件
"""

import time as _time_mod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union

from app.tools.toolhelper.date_helper import parse_datetime_any as _parse_datetime_any
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_TIME_DIFF


def _build_time_diff_llm_data(exec_code: str, duration_ms: int, humanized: str, seconds: int, days: float, is_future: bool) -> dict:
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


def time_diff(start: Union[int, float, str], end: Optional[Union[int, float, str]] = None) -> Dict[str, Any]:
    """计算时间差值 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        start_dt = _parse_datetime_any(start)
        if start_dt is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_time_diff_llm_data("error", duration_ms, "", 0, 0, False)
            return build_error(data={"error_detail": f"无法解析开始时间: {start}", "params": {"start": str(start)}}, llm_data=llm_data)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()

        if end is None:
            end_dt = datetime.now().astimezone()
        else:
            end_dt = _parse_datetime_any(end)
            if end_dt is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_time_diff_llm_data("error", duration_ms, "", 0, 0, False)
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
        llm_data = _build_time_diff_llm_data("success", duration_ms, humanized, seconds, days, is_future)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_diff_llm_data("error", duration_ms, "", 0, 0, False)
        return build_error(data={"error_detail": str(e), "params": {"start": str(start), "end": str(end)}}, llm_data=llm_data)


__all__ = ["time_diff"]