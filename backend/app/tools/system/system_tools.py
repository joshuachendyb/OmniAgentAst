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
import time
from typing import Optional, Dict, Any, List, Literal, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json as json_module

from app.utils.logger import logger
from app.utils.time_utils import now_str
from app.utils.tool_result_formatter import truncate_data_for_frontend, make_json_safe
from app.tools.tool_response import build_success, build_error  # 小沈 2026-05-20
from app.tools.tool_constants import TOOL_TIMEOUTS
# 【3.18修复 北京老陈 2026-05-31】超时常量统一到tool_constants.py
from app.tools.tool_constants import SUBPROCESS_TIMEOUT_DEFAULT





def get_system_info(info_type: str = "all") -> dict:
    """
    获取系统信息

    支持获取:基本信息、CPU信息、内存信息、磁盘信息、网络信息

    Args:
        info_type: 信息类型 (basic/cpu/memory/disk/network/all)

    Returns:
        {code, data, message}
    """
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

        return build_success(data, f"成功获取系统信息 ({info_type})",
                             llm_data={"action": "get_system_info", "info_type": info_type,
                                       "summary": f"已获取{info_type}类型的系统信息"})

    except Exception as e:
        logger.error(f"[get_system_info] 获取系统信息失败: {e}")
        return build_error(ERR_SYSTEM_INFO, f"获取系统信息失败: {str(e)}", data={"error": str(e)})


def event_log(
    log_name: str = "System",
    max_events: int = 50,
    level: str = "error",
    source: Optional[str] = None,
    time_range: str = "1h",
) -> dict:
    """
    获取系统事件日志 - 小沈 2026-05-02
    
    Windows使用wevtutil命令,Linux使用journalctl。
    """
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
            return _get_windows_event_log(log_name, max_events, level, source, start_time)
        else:
            return _get_linux_event_log(log_name, max_events, level, source, start_time)
    
    except Exception as e:
        logger.error(f"[event_log] 获取事件日志失败: {e}")
        return build_error(ERR_SYSTEM_EVENT_LOG, f"获取事件日志失败: {str(e)}", data={"error": str(e)})


def _get_windows_event_log(
    log_name: str,
    max_events: int,
    level: str,
    source: Optional[str],
    start_time: datetime,
) -> dict:
    """Windows事件日志获取"""
    try:
        level_map = {
            "critical": "Critical",
            "error": "Error",
            "warning": "Warning",
            "info": "Information",
        }
        win_level = level_map.get(level, "Error")
        
        # 小健 2026-05-19: 构造XPath查询含时间过滤
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
            return build_error(ERR_SYSTEM_EVENT_LOG, f"获取事件日志失败: {result.stderr}", data={"error": result.stderr})
        
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
        return build_success(truncate_data_for_frontend({
                "log_name": log_name,
                "events": _events,
                "total": len(_events),
                "level": level,
            }), f"找到 {len(_events)} 条事件日志", llm_data={
                "日志源": log_name, "条数": len(_events), "级别": level,
                "事件预览": make_json_safe(_events[:10], max_str_len=200)
            })
    
    except subprocess.TimeoutExpired:
        return build_error(ERR_SYSTEM_TIMEOUT, "获取事件日志超时")
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "wevtutil命令不存在")


def _get_linux_event_log(
    log_name: str,
    max_events: int,
    level: str,
    source: Optional[str],
    start_time: datetime,
) -> dict:
    """Linux事件日志获取(journalctl)"""
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
            return build_error(ERR_SYSTEM_EVENT_LOG, f"获取事件日志失败: {result.stderr}", data={"error": result.stderr})
        
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
        
        return build_success({
                "log_name": log_name,
                "events": events[:max_events],
                "total": len(events[:max_events]),
                "level": level,
            }, f"找到 {len(events[:max_events])} 条事件日志")
    
    except subprocess.TimeoutExpired:
        return build_error(ERR_SYSTEM_TIMEOUT, "获取事件日志超时")
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "journalctl命令不存在")




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


def _build_task_llm(tasks: List[Dict], total_raw: int,
                    total_matched: int, max_results: int) -> Dict:
    """构建 llm_data 摘要(移除 YAGNI 死代码 _llm["截断"])

    小沈 2026-05-25 重构拆分
    """
    return {
        "任务总数": total_raw,
        "过滤后": total_matched,
        "返回数": len(tasks),
        "任务列表": [{"名称": t.get("name", ""),
                    "状态": t.get("status_desc", t.get("status", ""))}
                   for t in tasks],
    }


def _task_list(
    filter_name: Optional[str] = None,
    filter_status: str = "all",
    max_results: int = 100,
) -> dict:
    """
    列出所有计划任务 - 小健 2026-05-06 参数名对齐Schema
    【小沈重构 2026-05-25】重构拆分:提取 _run_schtasks_query / _parse_task_entries / _filter_tasks / _build_task_llm

    使用schtasks query命令列出计划任务。

    Args:
        filter_name: 任务名称过滤(可选)
        filter_status: 状态过滤(ready/running/disabled/all)
        max_results: 最大返回数量

    Returns:
        {code, data, message}
    """
    try:
        if platform.system() != "Windows":
            return build_error(ERR_DESKTOP_PLATFORM_NOT_SUPPORTED, "task_list 仅支持Windows系统")

        stdout = _run_schtasks_query()
        tasks = _parse_task_entries(stdout)
        limited, matched = _filter_tasks(tasks, filter_name, filter_status, max_results)
        llm = _build_task_llm(limited, len(tasks), matched, max_results)

        return build_success({
            "tasks": limited,
            "total": len(limited),
            "total_matched": len(tasks),
            "platform": "Windows",
        }, f"找到 {len(tasks)} 个计划任务,返回前 {len(limited)} 个", llm_data=llm)

    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, "获取计划任务列表超时")
    except ValueError as e:                    # 小沈 2026-05-25: 恢复ERR_TASK_EMPTY专用错误码
        return build_error(ERR_TASK_EMPTY, str(e), data={"error": str(e)})
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "schtasks 命令不存在")
    except Exception as e:
        logger.error(f"[task_list] 获取计划任务列表失败: {e}")
        return build_error(ERR_TASK_LIST, f"获取计划任务列表失败: {str(e)}", data={"error": str(e)})


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
    """
    创建计划任务 - 小健 2026-05-06 补start_in对齐Schema
    
    使用schtasks create命令创建计划任务。
    
    Args:
        task_name: 计划任务名称
        command: 要执行的命令或程序路径
        schedule: 计划时间(格式:'HH:MM' 或 'HH:MM /day' 或 'HH:MM /monthly DD')
        start_time: 起始时间
        start_date: 起始日期
        interval: 重复间隔(分钟)
        description: 任务描述
        user: 运行任务的用户账户
    
    Returns:
        {code, data, message}
    """
    try:
        if platform.system() != "Windows":
            return build_error(ERR_DESKTOP_PLATFORM_NOT_SUPPORTED, "task_create 仅支持Windows系统")

        cmd = _build_schtasks_create_cmd(
            task_name, command, schedule,
            description, user, start_time, start_date, interval)

        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            return build_error(ERR_TASK_CREATE, f"创建计划任务失败: {result.stderr.strip() or result.stdout.strip()}", data={"error": result.stderr.strip() or result.stdout.strip()})

        return build_success({
                "task_name": task_name,
                "command": command,
                "schedule": schedule,
                "description": description,
                "user": user,
            }, f"计划任务 {task_name} 创建成功")

    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, "创建计划任务超时")
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "schtasks命令不存在")
    except Exception as e:
        logger.error(f"[task_create] 创建计划任务失败: {e}")
        return build_error(ERR_TASK_CREATE, f"创建计划任务失败: {str(e)}", data={"error": str(e)})


def _task_delete(
    task_name: str,
    force: bool = False,
    folder: Optional[str] = None,
) -> dict:
    """
    删除计划任务 - 小健 2026-05-06 补force对齐Schema
    
    使用schtasks delete命令删除计划任务。
    
    Args:
        task_name: 要删除的计划任务名称
        folder: 任务所在文件夹
    
    Returns:
        {code, data, message}
    """
    try:
        if platform.system() != "Windows":
            return build_error(ERR_DESKTOP_PLATFORM_NOT_SUPPORTED, "task_delete 仅支持Windows系统")
        
        # 处理完整的任务名(folder + task_name)
        full_task_name = task_name
        if folder:
            full_task_name = f"{folder}\\{task_name}"
        
        # 先查询确认任务存在
        query_cmd = ["schtasks", "/query", "/tn", full_task_name]
        query_result = subprocess.run(query_cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=SUBPROCESS_TIMEOUT_DEFAULT)
        
        if query_result.returncode != 0:
            return build_error(ERR_TASK_NOT_FOUND, f"计划任务 {full_task_name} 不存在", data={"name": full_task_name})
        
        cmd = ["schtasks", "/delete", "/tn", full_task_name, "/f"]
        
        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))
        
        if result.returncode != 0:
            return build_error(ERR_TASK_DELETE, f"删除计划任务失败: {result.stderr.strip() or result.stdout.strip()}", data={"error": result.stderr.strip() or result.stdout.strip()})
        
        delete_type = f"强制删除({folder})" if folder else "普通删除"
        
        return build_success({
                "task_name": full_task_name,
                "folder": folder,
                "delete_type": delete_type,
            }, f"计划任务 {full_task_name} 已删除")
    
    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, "删除计划任务超时")
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "schtasks命令不存在")
    except Exception as e:
        logger.error(f"[task_delete] 删除计划任务失败: {e}")
        return build_error(ERR_TASK_DELETE, f"删除计划任务失败: {str(e)}", data={"error": str(e)})



def create_task(
    task_name: str,
    command: str,
    schedule: str,
    interval: Optional[int] = None,
) -> dict:
    """
    创建Windows计划任务 - 小沈 2026-06-16, 小健 2026-06-20 删start_time(与schedule重叠)
    
    使用schtasks /create命令创建计划任务。
    schedule格式:'HH:MM'(每日)、'HH:MM /day N'(每周)、'HH:MM /monthly DD'(每月)
    
    Args:
        task_name: 计划任务名称(必填)
        command: 要执行的命令或程序路径(必填)
        schedule: 计划时间(必填)
        interval: 重复间隔分钟数(可选)
    
    Returns:
        {code, data, message}
    """
    start_time = None
    try:
        if platform.system() != "Windows":
            return build_error(ERR_DESKTOP_PLATFORM_NOT_SUPPORTED, "create_task 仅支持Windows系统")

        cmd = _build_schtasks_create_cmd(
            task_name, command, schedule,
            None, None, start_time, None, interval)

        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            return build_error(ERR_TASK_CREATE, f"创建计划任务失败: {result.stderr.strip() or result.stdout.strip()}", data={"error": result.stderr.strip() or result.stdout.strip()})

        return build_success({
                "task_name": task_name,
                "command": command,
                "schedule": schedule,
            }, f"计划任务 {task_name} 创建成功")

    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, "创建计划任务超时")
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "schtasks命令不存在")
    except Exception as e:
        logger.error(f"[create_task] 创建计划任务失败: {e}")
        return build_error(ERR_TASK_CREATE, f"创建计划任务失败: {str(e)}", data={"error": str(e)})


def delete_task(
    task_name: str,
) -> dict:
    """
    删除Windows计划任务 - 小沈 2026-06-16
    
    使用schtasks /delete命令删除计划任务。
    
    Args:
        task_name: 要删除的计划任务名称(必填)
    
    Returns:
        {code, data, message}
    """
    try:
        if platform.system() != "Windows":
            return build_error(ERR_DESKTOP_PLATFORM_NOT_SUPPORTED, "delete_task 仅支持Windows系统")

        query_cmd = ["schtasks", "/query", "/tn", task_name]
        query_result = subprocess.run(query_cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=SUBPROCESS_TIMEOUT_DEFAULT)

        if query_result.returncode != 0:
            return build_error(ERR_TASK_NOT_FOUND, f"计划任务 {task_name} 不存在", data={"name": task_name})

        cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]

        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            return build_error(ERR_TASK_DELETE, f"删除计划任务失败: {result.stderr.strip() or result.stdout.strip()}", data={"error": result.stderr.strip() or result.stdout.strip()})

        return build_success({
                "task_name": task_name,
            }, f"计划任务 {task_name} 已删除")

    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, "删除计划任务超时")
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "schtasks命令不存在")
    except Exception as e:
        logger.error(f"[delete_task] 删除计划任务失败: {e}")
        return build_error(ERR_TASK_DELETE, f"删除计划任务失败: {str(e)}", data={"error": str(e)})


def list_tasks(
    task_name: Optional[str] = None,
    state: str = "all",
) -> dict:
    """
    列出Windows计划任务 - 小沈 2026-06-16
    
    使用schtasks query命令列出计划任务。
    
    Args:
        task_name: 按任务名称过滤(模糊匹配,可选)
        state: 状态过滤(ready/running/disabled/all),默认all
    
    Returns:
        {code, data, message}
    """
    try:
        if platform.system() != "Windows":
            return build_error(ERR_DESKTOP_PLATFORM_NOT_SUPPORTED, "list_tasks 仅支持Windows系统")

        stdout = _run_schtasks_query()
        tasks = _parse_task_entries(stdout)
        limited, matched = _filter_tasks(tasks, task_name, state, 100)
        llm = _build_task_llm(limited, len(tasks), matched, 100)

        return build_success({
            "tasks": limited,
            "total": len(limited),
            "total_matched": len(tasks),
            "platform": "Windows",
        }, f"找到 {len(tasks)} 个计划任务,返回前 {len(limited)} 个", llm_data=llm)

    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, "获取计划任务列表超时")
    except ValueError as e:
        return build_error(ERR_TASK_EMPTY, str(e), data={"error": str(e)})
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "schtasks 命令不存在")
    except Exception as e:
        logger.error(f"[list_tasks] 获取计划任务列表失败: {e}")
        return build_error(ERR_TASK_LIST, f"获取计划任务列表失败: {str(e)}", data={"error": str(e)})
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
