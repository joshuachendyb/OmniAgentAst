# -*- coding: utf-8 -*-
"""
timer_clear — 清除定时器
【2026-06-22 小健】从 timer_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from typing import Dict, Any

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_TIMER_CLEAR
from app.tools.timer.timer_set import _timers, _timer_callbacks


def _build_timer_clear_llm_data(exec_code: str, duration_ms: int, timer_id: str, cancelled: bool) -> dict:
    """timer_clear的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"清除定时器失败: {timer_id}",
            "action": {"tool": "timer_clear", "tool_zh": "清除定时器", "target": timer_id, "params": {"timer_id": timer_id}},
            "status": {"exec_code": "error", "message": "清除定时器失败", "code": ERR_TIMER_CLEAR, "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    status_text = "已取消" if cancelled else "不存在或已触发"
    return {
        "summary": f"定时器 {timer_id} {status_text}",
        "action": {"tool": "timer_clear", "tool_zh": "清除定时器", "target": timer_id, "params": {"timer_id": timer_id}},
        "status": {"exec_code": "success", "message": f"定时器{status_text}", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


async def timer_clear(timer_id: str) -> Dict[str, Any]:
    """清除定时器 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        if timer_id not in _timers:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = {"timer_id": timer_id, "cancelled": False}
            llm_data = _build_timer_clear_llm_data("success", duration_ms, timer_id, False)
            return build_success(data=data, llm_data=llm_data)
        handle = _timers.pop(timer_id, None)
        if handle:
            handle.cancel()
        _timer_callbacks.pop(timer_id, None)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"timer_id": timer_id, "cancelled": True}
        llm_data = _build_timer_clear_llm_data("success", duration_ms, timer_id, True)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_clear_llm_data("error", duration_ms, timer_id, False)
        return build_error(data={"error_detail": str(e), "params": {"timer_id": timer_id}}, llm_data=llm_data)


__all__ = ["timer_clear"]