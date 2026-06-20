# -*- coding: utf-8 -*-
"""
Timer 工具函数模块 — 小欧 2026-06-17
从 meta/time_tools.py 迁移独立

3个公开工具:
- timer_set: 设置定时器
- timer_clear: 清除定时器
- timer_list: 列出所有定时器

Author: 小欧 - 2026-06-17
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.utils.logger import logger
from app.utils.time_utils import get_timestamp_ms
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import HTTPX_TIMEOUT_DEFAULT


# 定时器存储
_timers: Dict[str, asyncio.TimerHandle] = {}
_timer_counter = 0
_timer_callbacks: Dict[str, Dict[str, Any]] = {}
_timer_events: list[Dict[str, Any]] = []


def _error_timer_set(reason: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return build_error(
        ERR_TIMER_SET, reason,
        data=data or {},
    )


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


async def _timer_set(delay: float, callback: str) -> Dict[str, Any]:
    global _timer_counter
    if delay <= 0:
        return _error_timer_set("延迟时间必须大于0", data={"delay": delay})
    if delay > 86400:
        return _error_timer_set("延迟时间不能超过24小时", data={"delay": delay})

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

    return build_success({
        "timer_id": timer_id, "delay": delay,
        "trigger_at": trigger_at.strftime("%Y-%m-%d %H:%M:%S"),
        "message": f"定时器已设置,{int(delay / 60)}分钟后提醒",
    }, "定时器设置成功",
        llm_data={"timer_id": timer_id, "trigger_at": trigger_at.strftime("%Y-%m-%d %H:%M:%S")},
    )


async def timer_set(delay: float, callback: str) -> Dict[str, Any]:
    """设置定时器 — 小欧 2026-06-17"""
    try:
        result = await _timer_set(delay=delay, callback=callback)
        return result
    except Exception as e:
        return build_error(ERR_TIMER_SET, f"定时器设置失败: {str(e)}",
            data={"delay": delay, "callback": callback})


async def timer_clear(timer_id: str) -> Dict[str, Any]:
    """清除定时器 — 小欧 2026-06-17"""
    try:
        if timer_id not in _timers:
            return build_success(
                {"timer_id": timer_id, "cancelled": False},
                f"定时器 {timer_id} 已触发或不存在,无需取消",
            )
        handle = _timers.pop(timer_id, None)
        if handle:
            handle.cancel()
        _timer_callbacks.pop(timer_id, None)
        return build_success(
            {"timer_id": timer_id, "cancelled": True},
            "定时器已取消",
        )
    except Exception as e:
        return build_error(ERR_TIMER_CLEAR, f"清除定时器失败: {str(e)}",
            data={"timer_id": timer_id})


def timer_list() -> Dict[str, Any]:
    """列出所有活跃定时器 — 小欧 2026-06-17"""
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
        return build_success(
            timers,
            f"共{len(timers)}个定时器",
            llm_data={"count": len(timers), "ids": [t["timer_id"] for t in timers[:5]]},
        )
    except Exception as e:
        return build_error(ERR_TIMER_LIST, f"获取定时器列表失败: {str(e)}",
            data={})


from app.constants import (
    ERR_TIMER_CLEAR,
    ERR_TIMER_LIST,
    ERR_TIMER_SET,
)
