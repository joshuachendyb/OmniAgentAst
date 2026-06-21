# -*- coding: utf-8 -*-
"""
SYSTEM 工具函数模块 - 系统信息工具
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【创建时间】2026-04-29 小沈
【规范】按新规范使用 Pydantic 模型注册

包含:
- get_system_info: 获取系统信息
- event_log: 获取系统事件日志
- task_control: 计划任务统一控制(合并task_create/delete/list)
- registry_control: 注册表控制

返回格式:统一 {code, data, message} 格式

Author: 小沈 - 2026-04-29
"""

import os
import platform
import psutil
import socket
import subprocess
import re
import logging
import time as _time_mod
from typing import Optional, Dict, Any, List, Literal, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json as json_module

from app.utils.logger import logger
from app.utils.time_utils import now_str
from app.utils.tool_result_formatter import truncate_data_for_frontend, make_json_safe
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import TOOL_TIMEOUTS, SUBPROCESS_TIMEOUT_DEFAULT
from app.constants import (
    ERR_DESKTOP_PLATFORM_NOT_SUPPORTED,
    ERR_PARAMETER_INVALID,
    ERR_PERMISSION_DENIED,
    ERR_SERVICE_LIST,
    ERR_SERVICE_NOT_FOUND,
    ERR_SERVICE_START,
    ERR_SERVICE_STOP,
    ERR_SHELL_COMMAND_NOT_FOUND,
    ERR_SHELL_TIMEOUT,
    ERR_SYSTEM_EVENT_LOG,
    ERR_SYSTEM_INFO,
    ERR_SYSTEM_NET_CONN,
    ERR_SYSTEM_PROCESS_KILL,
    ERR_SYSTEM_PROCESS_LIST,
    ERR_SYSTEM_TIMEOUT,
    ERR_TASK_CREATE,
    ERR_TASK_DELETE,
    ERR_TASK_EMPTY,
    ERR_TASK_LIST,
    ERR_TASK_NOT_FOUND,
)





def _build_system_info_llm(exec_code: str, duration_ms: int, info_type: str) -> dict:
    """get_system_info的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"获取系统信息失败: {info_type}",
            "action": {"tool": "get_system_info", "tool_zh": "系统信息", "target": info_type, "params": {"info_type": info_type}},
            "status": {"exec_code": "error", "message": "获取系统信息失败", "code": ERR_SYSTEM_INFO, "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"已获取{info_type}类型的系统信息",
        "action": {"tool": "get_system_info", "tool_zh": "系统信息", "target": info_type, "params": {"info_type": info_type}},
        "status": {"exec_code": "success", "message": "获取系统信息成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def get_system_info(info_type: str = "all") -> dict:
    """获取系统信息 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        data = {}

        if info_type in ("basic", "all"):
            data["basic"] = {
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "hostname": socket.gethostname(),
                "python_version": platform.python_version(),
            }

        if info_type in ("cpu", "all"):
            cpu_freq = psutil.cpu_freq()
            data["cpu"] = {
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "current_frequency_mhz": cpu_freq.current if cpu_freq else None,
                "min_frequency_mhz": cpu_freq.min if cpu_freq else None,
                "max_frequency_mhz": cpu_freq.max if cpu_freq else None,
                "cpu_usage_percent": psutil.cpu_percent(interval=0.5),
            }

        if info_type in ("memory", "all"):
            mem = psutil.virtual_memory()
            data["memory"] = {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "percent": mem.percent,
            }

        if info_type in ("disk", "all"):
            disk_info = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "filesystem": partition.fstype,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent": usage.percent,
                    })
                except PermissionError:
                    continue
            data["disk"] = disk_info

        if info_type in ("network", "all"):
            net_io = psutil.net_io_counters()
            data["network"] = {
                "bytes_sent_mb": round(net_io.bytes_sent / (1024**2), 2),
                "bytes_recv_mb": round(net_io.bytes_recv / (1024**2), 2),
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
            }

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_system_info_llm("success", duration_ms, info_type)
        return build_success(data=data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"[get_system_info] 获取系统信息失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_system_info_llm("error", duration_ms, info_type)
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _build_event_log_llm(exec_code: str, duration_ms: int, log_name: str, event_count: int, level: str) -> dict:
    """event_log的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"获取事件日志失败: {log_name}",
            "action": {"tool": "event_log", "tool_zh": "事件日志", "target": log_name, "params": {"log_name": log_name, "level": level}},
            "status": {"exec_code": "error", "message": "获取事件日志失败", "code": ERR_SYSTEM_EVENT_LOG, "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"日志源 {log_name}，{event_count} 条{level}级别事件",
        "action": {"tool": "event_log", "tool_zh": "事件日志", "target": log_name, "params": {"log_name": log_name, "level": level}},
        "status": {"exec_code": "success", "message": "获取事件日志成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"events": {"value": event_count, "text": f"{event_count}条"}},
    }


def event_log(
    log_name: str = "System",
    max_events: int = 50,
    level: str = "error",
    source: Optional[str] = None,
    time_range: str = "1h",
) -> dict:
    """获取系统事件日志 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        time_map = {
            "10m": timedelta(minutes=10),
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
        }
        time_delta = time_map.get(time_range, timedelta(hours=1))
        start_time = datetime.now() - time_delta
        
        if platform.system() == "Windows":
            return _get_windows_event_log(log_name, max_events, level, source, start_time, t0)
        else:
            return _get_linux_event_log(log_name, max_events, level, source, start_time, t0)
    
    except Exception as e:
        logger.error(f"[event_log] 获取事件日志失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_event_log_llm("error", duration_ms, log_name, 0, level)
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _get_windows_event_log(
    log_name: str,
    max_events: int,
    level: str,
    source: Optional[str],
    start_time: datetime,
    t0: float = 0,
) -> dict:
    """Windows事件日志获取 — 小健 2026-06-21 builder改造"""
    try:
        level_map = {
            "critical": "Critical",
            "error": "Error",
            "warning": "Warning",
            "info": "Information",
        }
        win_level = level_map.get(level, "Error")
        
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        query_parts = [f"TimeCreated/@SystemTime >= '{start_time_str}'"]
        if level and level != "info":
            level_values = {"critical": "1", "error": "2", "warning": "3"}
            if level in level_values:
                query_parts.append(f"Level = {level_values[level]}")
        xpath_query = " and ".join(query_parts)
        
        cmd = [
            "wevtutil", "qe", log_name,
            f"/q:*[System[{xpath_query}]]",
            "/c:%d" % max_events,
            "/rd:true",
            "/f:text"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUTS.get("event_log", TOOL_TIMEOUTS["default"]))
        
        if result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000) if t0 else 0
            llm_data = _build_event_log_llm("error", duration_ms, log_name, 0, level)
            return build_error(data={"error_detail": result.stderr}, llm_data=llm_data)
        
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
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000) if t0 else 0
        data = truncate_data_for_frontend({
            "log_name": log_name,
            "events": _events,
            "total": len(_events),
            "level": level,
        })
        llm_data = _build_event_log_llm("success", duration_ms, log_name, len(_events), level)
        return build_success(data=data, llm_data=llm_data)
    
    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000) if t0 else 0
        llm_data = _build_event_log_llm("error", duration_ms, log_name, 0, level)
        llm_data["status"]["code"] = ERR_SYSTEM_TIMEOUT
        return build_error(data={"error_detail": "获取事件日志超时"}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000) if t0 else 0
        llm_data = _build_event_log_llm("error", duration_ms, log_name, 0, level)
        llm_data["status"]["code"] = ERR_SHELL_COMMAND_NOT_FOUND
        return build_error(data={"error_detail": "wevtutil命令不存在"}, llm_data=llm_data)


def _get_linux_event_log(
    log_name: str,
    max_events: int,
    level: str,
    source: Optional[str],
    start_time: datetime,
    t0: float = 0,
) -> dict:
    """Linux事件日志获取 — 小健 2026-06-21 builder改造"""
    try:
        level_map = {
            "critical": "emerg",
            "error": "err",
            "warning": "warning",
            "info": "info",
        }
        journal_level = level_map.get(level, "err")
        
        since_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        
        cmd = [
            "journalctl",
            f"--since={since_str}",
            f"--priority={journal_level}",
            f"--lines={max_events}",
            "--no-pager",
            "-o",
            "json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUTS.get("event_log", TOOL_TIMEOUTS["default"]))
        
        if result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000) if t0 else 0
            llm_data = _build_event_log_llm("error", duration_ms, log_name, 0, level)
            return build_error(data={"error_detail": result.stderr}, llm_data=llm_data)
        
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
        
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000) if t0 else 0
        data = {
            "log_name": log_name,
            "events": events[:max_events],
            "total": len(events[:max_events]),
            "level": level,
        }
        llm_data = _build_event_log_llm("success", duration_ms, log_name, len(events[:max_events]), level)
        return build_success(data=data, llm_data=llm_data)
    
    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000) if t0 else 0
        llm_data = _build_event_log_llm("error", duration_ms, log_name, 0, level)
        llm_data["status"]["code"] = ERR_SYSTEM_TIMEOUT
        return build_error(data={"error_detail": "获取事件日志超时"}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000) if t0 else 0
        llm_data = _build_event_log_llm("error", duration_ms, log_name, 0, level)
        llm_data["status"]["code"] = ERR_SHELL_COMMAND_NOT_FOUND
        return build_error(data={"error_detail": "journalctl命令不存在"}, llm_data=llm_data)




def _run_schtasks_query() -> str:
    """执行 schtasks /query /fo list /v,返回 stdout 文本。异常由内层抛出

    小沈 2026-05-25 重构拆分
    """
    cmd = ["schtasks", "/query", "/fo", "list", "/v"]
    result = subprocess.run(cmd, capture_output=True, encoding='gbk',
                            errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))
    if result.returncode != 0:
        raise RuntimeError(f"schtasks 执行失败: {result.stderr}")
    if not result.stdout:
        raise ValueError("计划任务列表为空")
    return result.stdout


def _parse_task_entries(stdout: str) -> List[Dict[str, str]]:
    """解析 schtasks /query /fo list /v 输出为结构化 dict 列表。
    可复用于 _task_detail(同样的 schtasks 输出格式)

    小沈 2026-05-25 重构拆分
    """
    tasks, current = [], {}
    for line in stdout.splitlines():
        s = line.strip()
        if s.startswith("TaskName:"):
            if current and "name" in current:
                tasks.append(current)
            current = {"name": s.split(":", 1)[1].strip()}
        elif s.startswith("Next Run Time:"):
            current["next_run"] = s.split(":", 1)[1].strip()
        elif s.startswith("Status:"):
            raw = s.split(":", 1)[1].strip()
            current["status"] = {"Ready": "ready", "Running": "running",
                                 "Disabled": "disabled"}.get(raw, "other")
            current["status_desc"] = raw
        elif s.startswith("Task To Run:"):
            current["command"] = s.split(":", 1)[1].strip()
    if current and "name" in current:
        tasks.append(current)
    return tasks


def _filter_tasks(tasks: List[Dict], filter_name: Optional[str],
                  filter_status: str, max_results: int) -> Tuple[List[Dict], int]:
    """过滤 + 截断,返回 (limited, matched_count)

    小沈 2026-05-25 重构拆分
    """
    matched = []
    for t in tasks:
        if filter_name and filter_name.lower() not in t.get("name", "").lower():
            continue
        if filter_status != "all" and t.get("status", "") != filter_status:
            continue
        matched.append(t)
    return matched[:max_results], len(matched)


def _build_task_llm(exec_code: str, duration_ms: int, tasks: List[Dict], total_raw: int,
                    total_matched: int) -> Dict:
    """构建 list_tasks 的 llm_data — 小健 2026-06-21 新5字段格式"""
    if exec_code == "error":
        return {
            "summary": "获取计划任务列表失败",
            "action": {"tool": "list_tasks", "tool_zh": "列出任务", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "获取计划任务列表失败", "code": ERR_TASK_LIST, "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"共 {total_raw} 个计划任务，匹配 {total_matched} 个，返回 {len(tasks)} 个",
        "action": {"tool": "list_tasks", "tool_zh": "列出任务", "target": "", "params": {}},
        "status": {"exec_code": "success", "message": "获取计划任务列表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"total": {"value": total_raw, "text": f"{total_raw}个"}, "matched": {"value": total_matched, "text": f"{total_matched}个"}},
    }


def _build_create_task_llm(exec_code: str, duration_ms: int, task_name: str, schedule: str = "",
                           err_code: str = "", detail: str = "") -> dict:
    """create_task的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"创建计划任务失败: {task_name}",
            "action": {"tool": "create_task", "tool_zh": "创建任务", "target": task_name, "params": {"task_name": task_name, "schedule": schedule}},
            "status": {"exec_code": "error", "message": "创建计划任务失败", "code": err_code or ERR_TASK_CREATE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"计划任务 {task_name} 创建成功",
        "action": {"tool": "create_task", "tool_zh": "创建任务", "target": task_name, "params": {"task_name": task_name, "schedule": schedule}},
        "status": {"exec_code": "success", "message": "创建计划任务成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_delete_task_llm(exec_code: str, duration_ms: int, task_name: str,
                           err_code: str = "", detail: str = "") -> dict:
    """delete_task的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"删除计划任务失败: {task_name}",
            "action": {"tool": "delete_task", "tool_zh": "删除任务", "target": task_name, "params": {"task_name": task_name}},
            "status": {"exec_code": "error", "message": "删除计划任务失败", "code": err_code or ERR_TASK_DELETE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"计划任务 {task_name} 已删除",
        "action": {"tool": "delete_task", "tool_zh": "删除任务", "target": task_name, "params": {"task_name": task_name}},
        "status": {"exec_code": "success", "message": "删除计划任务成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _task_list(
    filter_name: Optional[str] = None,
    filter_status: str = "all",
    max_results: int = 100,
) -> dict:
    """列出所有计划任务(内部) — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
            llm_data["status"]["code"] = ERR_DESKTOP_PLATFORM_NOT_SUPPORTED
            return build_error(data={"error_detail": "task_list 仅支持Windows系统"}, llm_data=llm_data)

        stdout = _run_schtasks_query()
        tasks = _parse_task_entries(stdout)
        limited, matched = _filter_tasks(tasks, filter_name, filter_status, max_results)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {
            "tasks": limited,
            "total": len(limited),
            "total_matched": len(tasks),
            "platform": "Windows",
        }
        llm_data = _build_task_llm("success", duration_ms, limited, len(tasks), matched)
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
        llm_data["status"]["code"] = ERR_SHELL_TIMEOUT
        return build_error(data={"error_detail": "获取计划任务列表超时"}, llm_data=llm_data)
    except ValueError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
        llm_data["status"]["code"] = ERR_TASK_EMPTY
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
        llm_data["status"]["code"] = ERR_SHELL_COMMAND_NOT_FOUND
        return build_error(data={"error_detail": "schtasks 命令不存在"}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[task_list] 获取计划任务列表失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _build_schtasks_create_cmd(
    task_name: str,
    command: str,
    schedule: str,
    description: Optional[str] = None,
    user: Optional[str] = None,
    start_time: Optional[str] = None,
    start_date: Optional[str] = None,
    interval: Optional[int] = None,
) -> list:
    """构建 schtasks /create 命令参数列表 — 纯函数,无IO — 小沈 2026-05-25"""
    cmd = ["schtasks", "/create", "/tn", task_name, "/tr", command]

    schedule_parts = schedule.split()
    time_part = schedule_parts[0]

    sc_type = "daily"
    sc_extra = []
    if len(schedule_parts) > 1:
        if "/day" in schedule_parts:
            day_idx = schedule_parts.index("/day")
            if day_idx + 1 < len(schedule_parts):
                day_num = schedule_parts[day_idx + 1]
                sc_type = "weekly"
                day_name = "MON,TUE,WED,THU,FRI,SAT,SUN".split(",")[int(day_num)-1] if day_num.isdigit() else day_num
                sc_extra = ["/d", day_name]
        elif "/monthly" in schedule_parts:
            monthly_idx = schedule_parts.index("/monthly")
            if monthly_idx + 1 < len(schedule_parts):
                day_num = schedule_parts[monthly_idx + 1]
                sc_type = "monthly"
                sc_extra = ["/d", day_num]

    if start_time:
        cmd.extend(["/st", start_time])
    else:
        cmd.extend(["/st", time_part])
    if description:
        cmd.extend(["/tn", description])
    if user:
        cmd.extend(["/ru", user])
    if start_date:
        cmd.extend(["/sd", start_date])
    if interval and interval > 0:
        cmd.extend(["/ri", str(interval)])

    cmd.append("/f")
    return cmd


def _task_create(
    task_name: str,
    command: str,
    schedule: str,
    description: Optional[str] = None,
    user: Optional[str] = None,
    start_in: Optional[str] = None,
    start_time: Optional[str] = None,
    start_date: Optional[str] = None,
    interval: Optional[int] = None,
) -> dict:
    """创建计划任务(内部) — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_DESKTOP_PLATFORM_NOT_SUPPORTED)
            return build_error(data={"error_detail": "task_create 仅支持Windows系统"}, llm_data=llm_data)

        cmd = _build_schtasks_create_cmd(
            task_name, command, schedule,
            description, user, start_time, start_date, interval)

        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            err_msg = result.stderr.strip() or result.stdout.strip()
            llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_TASK_CREATE, err_msg)
            return build_error(data={"error_detail": err_msg}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"task_name": task_name, "command": command, "schedule": schedule, "description": description, "user": user}
        llm_data = _build_create_task_llm("success", duration_ms, task_name, schedule)
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_SHELL_TIMEOUT)
        return build_error(data={"error_detail": "创建计划任务超时"}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_SHELL_COMMAND_NOT_FOUND)
        return build_error(data={"error_detail": "schtasks命令不存在"}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[task_create] 创建计划任务失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_TASK_CREATE, str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _task_delete(
    task_name: str,
    force: bool = False,
    folder: Optional[str] = None,
) -> dict:
    """删除计划任务(内部) — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_DESKTOP_PLATFORM_NOT_SUPPORTED)
            return build_error(data={"error_detail": "task_delete 仅支持Windows系统"}, llm_data=llm_data)
        
        full_task_name = task_name
        if folder:
            full_task_name = f"{folder}\\{task_name}"
        
        query_cmd = ["schtasks", "/query", "/tn", full_task_name]
        query_result = subprocess.run(query_cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=SUBPROCESS_TIMEOUT_DEFAULT)
        
        if query_result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_delete_task_llm("error", duration_ms, full_task_name, ERR_TASK_NOT_FOUND)
            return build_error(data={"error_detail": f"计划任务 {full_task_name} 不存在", "params": {"name": full_task_name}}, llm_data=llm_data)
        
        cmd = ["schtasks", "/delete", "/tn", full_task_name, "/f"]
        
        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))
        
        if result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            err_msg = result.stderr.strip() or result.stdout.strip()
            llm_data = _build_delete_task_llm("error", duration_ms, full_task_name, ERR_TASK_DELETE, err_msg)
            return build_error(data={"error_detail": err_msg}, llm_data=llm_data)
        
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"task_name": full_task_name, "folder": folder, "delete_type": f"强制删除({folder})" if folder else "普通删除"}
        llm_data = _build_delete_task_llm("success", duration_ms, full_task_name)
        return build_success(data=data, llm_data=llm_data)
    
    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_SHELL_TIMEOUT)
        return build_error(data={"error_detail": "删除计划任务超时"}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_SHELL_COMMAND_NOT_FOUND)
        return build_error(data={"error_detail": "schtasks命令不存在"}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[task_delete] 删除计划任务失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_TASK_DELETE, str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)



def create_task(
    task_name: str,
    command: str,
    schedule: str,
    interval: Optional[int] = None,
) -> dict:
    """创建Windows计划任务 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_DESKTOP_PLATFORM_NOT_SUPPORTED)
            return build_error(data={"error_detail": "create_task 仅支持Windows系统"}, llm_data=llm_data)

        cmd = _build_schtasks_create_cmd(
            task_name, command, schedule,
            None, None, None, None, interval)

        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            err_msg = result.stderr.strip() or result.stdout.strip()
            llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_TASK_CREATE, err_msg)
            return build_error(data={"error_detail": err_msg}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"task_name": task_name, "command": command, "schedule": schedule}
        llm_data = _build_create_task_llm("success", duration_ms, task_name, schedule)
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_SHELL_TIMEOUT)
        return build_error(data={"error_detail": "创建计划任务超时"}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_SHELL_COMMAND_NOT_FOUND)
        return build_error(data={"error_detail": "schtasks命令不存在"}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[create_task] 创建计划任务失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm("error", duration_ms, task_name, schedule, ERR_TASK_CREATE, str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def delete_task(
    task_name: str,
) -> dict:
    """删除Windows计划任务 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_DESKTOP_PLATFORM_NOT_SUPPORTED)
            return build_error(data={"error_detail": "delete_task 仅支持Windows系统"}, llm_data=llm_data)

        query_cmd = ["schtasks", "/query", "/tn", task_name]
        query_result = subprocess.run(query_cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=SUBPROCESS_TIMEOUT_DEFAULT)

        if query_result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_TASK_NOT_FOUND)
            return build_error(data={"error_detail": f"计划任务 {task_name} 不存在", "params": {"name": task_name}}, llm_data=llm_data)

        cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]

        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            err_msg = result.stderr.strip() or result.stdout.strip()
            llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_TASK_DELETE, err_msg)
            return build_error(data={"error_detail": err_msg}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"task_name": task_name}
        llm_data = _build_delete_task_llm("success", duration_ms, task_name)
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_SHELL_TIMEOUT)
        return build_error(data={"error_detail": "删除计划任务超时"}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_SHELL_COMMAND_NOT_FOUND)
        return build_error(data={"error_detail": "schtasks命令不存在"}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[delete_task] 删除计划任务失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_task_llm("error", duration_ms, task_name, ERR_TASK_DELETE, str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def list_tasks(
    task_name: Optional[str] = None,
    state: str = "all",
) -> dict:
    """列出Windows计划任务 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
            llm_data["status"]["code"] = ERR_DESKTOP_PLATFORM_NOT_SUPPORTED
            return build_error(data={"error_detail": "list_tasks 仅支持Windows系统"}, llm_data=llm_data)

        stdout = _run_schtasks_query()
        tasks = _parse_task_entries(stdout)
        limited, matched = _filter_tasks(tasks, task_name, state, 100)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"tasks": limited, "total": len(limited), "total_matched": len(tasks), "platform": "Windows"}
        llm_data = _build_task_llm("success", duration_ms, limited, len(tasks), matched)
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
        llm_data["status"]["code"] = ERR_SHELL_TIMEOUT
        return build_error(data={"error_detail": "获取计划任务列表超时"}, llm_data=llm_data)
    except ValueError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
        llm_data["status"]["code"] = ERR_TASK_EMPTY
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
        llm_data["status"]["code"] = ERR_SHELL_COMMAND_NOT_FOUND
        return build_error(data={"error_detail": "schtasks 命令不存在"}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[list_tasks] 获取计划任务列表失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_task_llm("error", duration_ms, [], 0, 0)
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)

