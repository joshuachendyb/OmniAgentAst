# -*- coding: utf-8 -*-
"""
Timer 工具函数模块 — 小欧 2026-06-17
从 meta/time_tools.py 迁移独立

3个公开工具:
- timer_set: 设置定时器
- timer_clear: 清除定时器
- timer_list: 列出所有定时器

【2026-06-21 小健】Phase 1 builder改造: build_success/error适配新3字段签名

Author: 小欧 - 2026-06-17
"""

import asyncio
import time as _time_mod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.utils.logger import logger
from app.utils.time_utils import get_timestamp_ms
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import HTTPX_TIMEOUT_DEFAULT
from app.constants import (
    ERR_TIMER_CLEAR,
    ERR_TIMER_LIST,
    ERR_TIMER_SET,
)


_timers: Dict[str, asyncio.TimerHandle] = {}
_timer_counter = 0
_timer_callbacks: Dict[str, Dict[str, Any]] = {}
_timer_events: list[Dict[str, Any]] = []


def _build_timer_set_llm(exec_code: str, duration_ms: int, timer_id: str, trigger_at: str, delay: float) -> dict:
    """timer_set的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"定时器设置失败: {delay}秒",
            "action": {"tool": "timer_set", "tool_zh": "设置定时器", "target": str(delay), "params": {"delay": delay}},
            "status": {"exec_code": "error", "message": "定时器设置失败", "code": ERR_TIMER_SET, "detail": "", "hint": "请检查延迟时间"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"定时器 {timer_id}，{int(delay / 60)}分钟后触发",
        "action": {"tool": "timer_set", "tool_zh": "设置定时器", "target": str(delay), "params": {"delay": delay}},
        "status": {"exec_code": "success", "message": "定时器设置成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"delay": {"value": delay, "text": f"{int(delay / 60)}分钟"}},
    }


def _build_timer_clear_llm(exec_code: str, duration_ms: int, timer_id: str, cancelled: bool) -> dict:
    """timer_clear的llm_data构建函数 — 小健 2026-06-21"""
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


def _build_timer_list_llm(exec_code: str, duration_ms: int, count: int, ids: list) -> dict:
    """timer_list的llm_data构建函数 — 小健 2026-06-21"""
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


async def _invoke_timer_callback(timer_id: str, callback: str) -> Dict[str, Any]:
    event = {
        "timer_id": timer_id,
        "triggered_at": datetime.now().astimezone().isoformat(),
        "callback": callback,
        "status": "triggered",
    }
    try:
        if not callback.strip().startswith("http"):
            logger.info(f"[Timer {timer_id}] 提醒: {callback}")
            event["executed_as"] = "log_message"
        else:
            import httpx
            resp = httpx.get(callback, timeout=HTTPX_TIMEOUT_DEFAULT)
            event["executed_as"] = "http_call"
            event["http_status"] = resp.status_code
    except httpx.TimeoutException:
        event["executed_as"] = "http_timeout"
    except Exception as e:
        event["executed_as"] = "http_call_failed"
        event["error"] = str(e)
    return event


async def timer_set(delay: float, callback: str) -> Dict[str, Any]:
    """设置定时器 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    global _timer_counter
    try:
        if delay <= 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_timer_set_llm("error", duration_ms, "", "", delay)
            return build_error(data={"error_detail": "延迟时间必须大于0", "params": {"delay": delay}}, llm_data=llm_data)
        if delay > 86400:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_timer_set_llm("error", duration_ms, "", "", delay)
            return build_error(data={"error_detail": "延迟时间不能超过24小时", "params": {"delay": delay}}, llm_data=llm_data)

        _timer_counter += 1
        timer_id = f"timer_{_timer_counter}_{get_timestamp_ms()}"
        trigger_at = datetime.now().astimezone() + timedelta(seconds=delay)

        _timer_callbacks[timer_id] = {
            "callback": callback,
            "created_at": datetime.now().astimezone().isoformat(),
            "trigger_at": trigger_at.isoformat(),
        }

        async def _timer_cb():
            event = await _invoke_timer_callback(timer_id, callback)
            _timer_events.append(event)

        loop = asyncio.get_running_loop()
        timer_handle = loop.call_later(delay, lambda: asyncio.create_task(_timer_cb()))
        _timers[timer_id] = timer_handle

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {
            "timer_id": timer_id, "delay": delay,
            "trigger_at": trigger_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        llm_data = _build_timer_set_llm("success", duration_ms, timer_id, trigger_at.strftime("%Y-%m-%d %H:%M:%S"), delay)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_set_llm("error", duration_ms, "", "", delay)
        return build_error(data={"error_detail": str(e), "params": {"delay": delay, "callback": callback}}, llm_data=llm_data)


async def timer_clear(timer_id: str) -> Dict[str, Any]:
    """清除定时器 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if timer_id not in _timers:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = {"timer_id": timer_id, "cancelled": False}
            llm_data = _build_timer_clear_llm("success", duration_ms, timer_id, False)
            return build_success(data=data, llm_data=llm_data)
        handle = _timers.pop(timer_id, None)
        if handle:
            handle.cancel()
        _timer_callbacks.pop(timer_id, None)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"timer_id": timer_id, "cancelled": True}
        llm_data = _build_timer_clear_llm("success", duration_ms, timer_id, True)
        return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_clear_llm("error", duration_ms, timer_id, False)
        return build_error(data={"error_detail": str(e), "params": {"timer_id": timer_id}}, llm_data=llm_data)


def timer_list() -> Dict[str, Any]:
    """列出所有活跃定时器 — 小健 2026-06-21 builder改造"""
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
        llm_data = _build_timer_list_llm("success", duration_ms, len(timers), [t["timer_id"] for t in timers[:5]])
        return build_success(data=timers, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_list_llm("error", duration_ms, 0, [])
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)
