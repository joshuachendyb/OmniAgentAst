# -*- coding: utf-8 -*-
"""
timer_list — 列出所有定时器
【2026-06-22 小健】从 timer_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_TIMER_LIST
from app.tools.timer.timer_set import _timer_callbacks


def _build_timer_list_llm_data(exec_code: str, duration_ms: int, count: int, ids: list) -> dict:
    """timer_list的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": "获取定时器列表失败",
            "action": {"tool": "timer_list", "tool_zh": "列出定时器", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "获取定时器列表失败", "code": ERR_TIMER_LIST, "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"共 {count} 个定时器",
        "action": {"tool": "timer_list", "tool_zh": "列出定时器", "target": "", "params": {}},
        "status": {"exec_code": "success", "message": "获取定时器列表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"count": {"value": count, "text": f"{count}个"}},
    }


def timer_list() -> Dict[str, Any]:
    """列出所有活跃定时器 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        timers = []
        for timer_id, info in _timer_callbacks.items():
            timers.append({
                "timer_id": timer_id,
                "callback": info.get("callback", ""),
                "created_at": info.get("created_at", ""),
                "trigger_at": info.get("trigger_at", ""),
            })
        timers.sort(key=lambda x: x.get("trigger_at", ""))
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_list_llm_data("success", duration_ms, len(timers), [t["timer_id"] for t in timers[:5]])
        return build_success(data=timers, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_list_llm_data("error", duration_ms, 0, [])
        return build_error(data={"error_detail": str(e), "params": {}}, llm_data=llm_data)


__all__ = ["timer_list"]