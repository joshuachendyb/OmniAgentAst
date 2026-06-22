# -*- coding: utf-8 -*-
"""
event_log — 获取系统事件日志
【2026-06-22 小健】从 system_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import json as json_module
import platform
import subprocess
import time as _time_mod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import TOOL_TIMEOUTS
from app.constants import (
    ERR_SHELL_COMMAND_NOT_FOUND,
    ERR_SHELL_TIMEOUT,
    ERR_SYSTEM_EVENT_LOG,
    ERR_SYSTEM_TIMEOUT,
)


def _build_event_log_llm_data(exec_code: str, duration_ms: int, log_name: str, event_count: int, level: str, detail: str = "") -> dict:
    """event_log的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"获取失败: {detail}" if detail else f"获取事件日志失败: {log_name}",
            "action": {"tool": "event_log", "tool_zh": "获取", "target": log_name, "params": {"log_name": log_name, "level": level}},
            "status": {"exec_code": "error", "message": "获取事件日志失败", "code": ERR_SYSTEM_EVENT_LOG, "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"获取 {log_name}，{event_count}条事件",
        "action": {"tool": "event_log", "tool_zh": "获取", "target": log_name, "params": {"log_name": log_name, "level": level}},
        "status": {"exec_code": "success", "message": "获取成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"events": {"value": event_count, "text": f"{event_count}条"}},
    }


def _get_windows_event_log(log_name: str, max_events: int, level: str,
                           source: Optional[str], start_time: datetime) -> dict:
    """Windows事件日志获取 — 小健 2026-06-22（返回原始dict，不含build3/llm_data）"""
    try:
        level_map = {"critical": "Critical", "error": "Error", "warning": "Warning", "info": "Information"}
        win_level = level_map.get(level, "Error")

        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        query_parts = [f"TimeCreated/@SystemTime >= '{start_time_str}'"]
        if level and level != "info":
            level_values = {"critical": "1", "error": "2", "warning": "3"}
            if level in level_values:
                query_parts.append(f"Level = {level_values[level]}")
        xpath_query = " and ".join(query_parts)

        cmd = ["wevtutil", "qe", log_name, f"/q:*[System[{xpath_query}]]", "/c:%d" % max_events, "/rd:true", "/f:text"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUTS.get("event_log", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            return {"error_detail": result.stderr, "params": {"log_name": log_name}, "_error_code": ERR_SYSTEM_EVENT_LOG}

        events = []
        current_event = {}
        for line in result.stdout.splitlines():
            if line.startswith("Event["):
                if current_event:
                    events.append(current_event)
                current_event = {}
            elif ":" in line and current_event is not None:
                key, value = line.split(":", 1)
                current_event[key.strip()] = value.strip()
        if current_event:
            events.append(current_event)

        filtered_events = []
        for evt in events:
            evt_level = evt.get("Level", "")
            if level and win_level.lower() not in evt_level.lower():
                continue
            if source:
                evt_source = evt.get("Source Name", "")
                if source.lower() not in evt_source.lower():
                    continue
            filtered_events.append(evt)

        _events = filtered_events[:max_events]
        return {"events": _events}

    except subprocess.TimeoutExpired:
        return {"error_detail": "获取事件日志超时", "params": {"log_name": log_name}, "_error_code": ERR_SYSTEM_TIMEOUT}
    except FileNotFoundError:
        return {"error_detail": "wevtutil命令不存在", "params": {"log_name": log_name}, "_error_code": ERR_SHELL_COMMAND_NOT_FOUND}
    except Exception as e:
        return {"error_detail": str(e), "params": {"log_name": log_name}, "_error_code": ERR_SYSTEM_EVENT_LOG}


def _get_linux_event_log(log_name: str, max_events: int, level: str,
                         source: Optional[str], start_time: datetime) -> dict:
    """Linux事件日志获取 — 小健 2026-06-22（返回原始dict，不含build3/llm_data）"""
    try:
        level_map = {"critical": "emerg", "error": "err", "warning": "warning", "info": "info"}
        journal_level = level_map.get(level, "err")
        since_str = start_time.strftime("%Y-%m-%d %H:%M:%S")

        cmd = ["journalctl", f"--since={since_str}", f"--priority={journal_level}", f"--lines={max_events}", "--no-pager", "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUTS.get("event_log", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            return {"error_detail": result.stderr, "params": {"log_name": log_name}, "_error_code": ERR_SYSTEM_EVENT_LOG}

        events = []
        for line in result.stdout.splitlines():
            if line.strip():
                try:
                    evt = json_module.loads(line)
                    events.append({
                        "timestamp": evt.get("__REALTIME_TIMESTAMP", ""),
                        "hostname": evt.get("_HOSTNAME", ""),
                        "syslog_identifier": evt.get("SYSLOG_IDENTIFIER", ""),
                        "message": evt.get("MESSAGE", ""),
                        "priority": evt.get("PRIORITY", ""),
                    })
                except json_module.JSONDecodeError:
                    continue

        return {"events": events[:max_events]}

    except subprocess.TimeoutExpired:
        return {"error_detail": "获取事件日志超时", "params": {"log_name": log_name}, "_error_code": ERR_SYSTEM_TIMEOUT}
    except FileNotFoundError:
        return {"error_detail": "journalctl命令不存在", "params": {"log_name": log_name}, "_error_code": ERR_SHELL_COMMAND_NOT_FOUND}
    except Exception as e:
        return {"error_detail": str(e), "params": {"log_name": log_name}, "_error_code": ERR_SYSTEM_EVENT_LOG}


def event_log(log_name: str = "System", max_events: int = 50, level: str = "error",
              source: Optional[str] = None, time_range: str = "1h") -> dict:
    """获取系统事件日志 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        time_map = {"10m": timedelta(minutes=10), "1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7)}
        time_delta = time_map.get(time_range, timedelta(hours=1))
        start_time = datetime.now() - time_delta

        if platform.system() == "Windows":
            result = _get_windows_event_log(log_name, max_events, level, source, start_time)
        else:
            result = _get_linux_event_log(log_name, max_events, level, source, start_time)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

        if "error_detail" in result:
            error_code = result.pop("_error_code", ERR_SYSTEM_EVENT_LOG)
            llm_data = _build_event_log_llm_data("error", duration_ms, log_name, 0, level)
            llm_data["status"]["code"] = error_code
            return build_error(data=result, llm_data=llm_data)
        else:
            result.pop("_error_code", None)
            event_count = len(result.get("events", []))
            llm_data = _build_event_log_llm_data("success", duration_ms, log_name, event_count, level)
            return build_success(data=result, llm_data=llm_data)

    except Exception as e:
        logger.error(f"[event_log] 获取事件日志失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_event_log_llm_data("error", duration_ms, log_name, 0, level)
        return build_error(data={"error_detail": str(e), "params": {"log_name": log_name}}, llm_data=llm_data)


__all__ = ["event_log"]