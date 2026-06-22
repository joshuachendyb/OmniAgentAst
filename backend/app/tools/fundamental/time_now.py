# -*- coding: utf-8 -*-
"""
time_now — 获取当前系统时间
【2026-06-22 小健】从 time_tools.py 拆分为独立文件
"""

import time as _time_mod
from datetime import datetime
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_TIME_NOW


def _build_time_now_llm_data(exec_code: str, duration_ms: int, iso: str, formatted: str, weekday: str) -> dict:
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


def time_now() -> Dict[str, Any]:
    """获取当前系统时间 — 小欧 2026-06-17 只保留"now"操作; 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
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
        llm_data = _build_time_now_llm_data("success", duration_ms, now.isoformat(), formatted, now.strftime("%A"))
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_time_now_llm_data("error", duration_ms, "", "", "")
        return build_error(data={"error_detail": str(e), "params": {"timezone": timezone}}, llm_data=llm_data)


__all__ = ["time_now"]