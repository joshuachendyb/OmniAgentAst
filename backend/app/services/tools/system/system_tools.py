# -*- coding: utf-8 -*-
"""
SYSTEM 工具函数模块 - 系统信息工具

【创建时间】2026-04-29 小沈
【规范】按新规范使用 Pydantic 模型注册

包含：
- get_system_info: 获取系统信息
- net_connections: 获取网络连接列表
- event_log: 获取系统事件日志
- list_processes: 列出所有进程
- kill_process: 终止指定进程
- service_control: 服务统一控制（合并service_start/stop/list）
- task_control: 计划任务统一控制（合并task_create/delete/list）
- get_env: 获取/列出环境变量
- set_env: 设置/删除环境变量
- registry_control: 注册表控制

返回格式：统一 {code, data, message} 格式

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
from app.services.tools.tool_result_utils import build_next_actions, truncate_data_for_frontend, make_json_safe
from app.services.tools._response import build_success, build_error  # 小沈 2026-05-20





def get_system_info(info_type: str = "all") -> dict:
    """
    获取系统信息

    支持获取：基本信息、CPU信息、内存信息、磁盘信息、网络信息

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

        return build_success(data, f"成功获取系统信息 ({info_type})", next_actions=build_next_actions([("list_processes", "查看进程详情", "需要进一步排查时"), ("net_connections", "查看网络连接", "需要排查网络时")]))

    except Exception as e:
        logger.error(f"[get_system_info] 获取系统信息失败: {e}")
        return build_error(ERR_SYSTEM_INFO, f"获取系统信息失败: {str(e)}")


def net_connections(
    kind: str = "inet",
    state: Optional[str] = None,
    process_info: bool = False,
    filter_port: Optional[int] = None,
) -> dict:
    """
    获取网络连接列表 - 小沈 2026-05-02
    
    使用psutil获取网络连接信息。
    支持按类型、状态、端口过滤。
    """
    # ⚠️ 警告: 以下参数已从Schema移除，硬编码默认值，后续视需求决定是否恢复
    resolve_dns: bool = False
    try:
        # 小健 2026-05-19: tcp/udp应包含inet4+inet6
        conn_kind_map = {
            "inet": "inet",
            "tcp": "inet",
            "udp": "inet",
        }
        
        connections = psutil.net_connections(kind=conn_kind_map.get(kind, "inet"))
        
        results = []
        for conn in connections:
            if len(results) >= 200:
                break
            
            if kind == "tcp" and conn.type != socket.SOCK_STREAM:
                continue
            if kind == "udp" and conn.type != socket.SOCK_DGRAM:
                continue
            
            if state:
                conn_state = (conn.status or "").lower()
                if state.lower() not in conn_state:
                    continue
            
            local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
            remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
            
            if filter_port:
                local_port = conn.laddr.port if conn.laddr else None
                remote_port = conn.raddr.port if conn.raddr else None
                if local_port != filter_port and remote_port != filter_port:
                    continue
            
            conn_info = {
                "fd": conn.fd,
                "family": conn.family.name if hasattr(conn.family, 'name') else str(conn.family),
                "type": "TCP" if conn.type == socket.SOCK_STREAM else "UDP",
                "local_address": local_addr,
                "remote_address": remote_addr,
                "status": conn.status if conn.status else "N/A",
                "pid": conn.pid,
            }
            
            if process_info and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    conn_info["process_name"] = proc.name()
                    conn_info["process_exe"] = proc.exe()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    conn_info["process_name"] = "N/A"
                    conn_info["process_exe"] = "N/A"
            
            results.append(conn_info)
        
        return build_success(truncate_data_for_frontend({
                "connections": results,
                "total": len(results),
                "kind": kind,
                "filter_port": filter_port,
            }), f"找到 {len(results)} 个网络连接", llm_data={
                "总数": len(results), "类型": kind,
                "连接预览": make_json_safe(results[:20], max_str_len=100)
            }, next_actions=build_next_actions([("get_system_info", "查看系统总览", "需要更多系统信息时")]))
    
    except psutil.AccessDenied:
        return build_error(ERR_PERMISSION_DENIED, "需要管理员权限获取网络连接信息，请以管理员身份运行")
    except Exception as e:
        logger.error(f"[net_connections] 获取网络连接失败: {e}")
        return build_error(ERR_SYSTEM_NET_CONN, f"获取网络连接失败: {str(e)}")


def event_log(
    log_name: str = "System",
    max_events: int = 50,
    level: str = "error",
    source: Optional[str] = None,
    time_range: str = "1h",
) -> dict:
    """
    获取系统事件日志 - 小沈 2026-05-02
    
    Windows使用wevtutil命令，Linux使用journalctl。
    """
    # ⚠️ 警告: 以下参数已从Schema移除，硬编码默认值，后续视需求决定是否恢复
    event_id: Optional[List[int]] = None
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
        return build_error(ERR_SYSTEM_EVENT_LOG, f"获取事件日志失败: {str(e)}")


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
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return build_error(ERR_SYSTEM_EVENT_LOG, f"获取事件日志失败: {result.stderr}")
        
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
            }, next_actions=build_next_actions([("get_system_info", "查看系统状态", "需要关联系统信息时")]))
    
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
    """Linux事件日志获取（journalctl）"""
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
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return build_error(ERR_SYSTEM_EVENT_LOG, f"获取事件日志失败: {result.stderr}")
        
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
            }, f"找到 {len(events[:max_events])} 条事件日志", next_actions=build_next_actions([("get_system_info", "查看系统状态", "需要关联系统信息时")]))
    
    except subprocess.TimeoutExpired:
        return build_error(ERR_SYSTEM_TIMEOUT, "获取事件日志超时")
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "journalctl命令不存在")


def _filter_process(
    proc_info: dict,
    filter_name: Optional[str] = None,
    filter_pid: Optional[int] = None,
    user: Optional[str] = None,
    status: Optional[str] = None,
) -> bool:
    """进程过滤谓词 — 纯函数 — 小沈 2026-05-25"""
    if filter_name:
        pn = proc_info.get('name', '')
        if filter_name.lower() not in pn.lower():
            return False
    if filter_pid:
        if proc_info.get('pid') != filter_pid:
            return False
    if user:
        pu = proc_info.get('username', '') or ''
        if user.lower() not in pu.lower():
            return False
    if status:
        ps = proc_info.get('status', '') or ''
        if status.lower() not in ps.lower():
            return False
    return True


def _format_process(proc_info: dict) -> dict:
    """格式化单个进程信息为输出字典 — 小沈 2026-05-25"""
    cpu = proc_info.get('cpu_percent') or 0.0
    mem = proc_info.get('memory_percent') or 0.0
    return {
        "pid": proc_info['pid'],
        "name": proc_info.get('name', 'N/A'),
        "status": proc_info.get('status', 'N/A'),
        "user": proc_info.get('username', 'N/A'),
        "cpu_percent": round(cpu, 2),
        "memory_percent": round(mem, 2),
        "exe": proc_info.get('exe', 'N/A'),
        "cmdline": ' '.join(proc_info.get('cmdline', []))[:200] if proc_info.get('cmdline') else 'N/A',
    }


def list_processes(
    filter_name: Optional[str] = None,
    filter_pid: Optional[int] = None,
    user: Optional[str] = None,
    sort_by: str = "pid",
    max_results: int = 100,
) -> dict:
    """
    列出所有进程 - 小健 2026-05-06 补user/status/limit对齐Schema
    
    按文档7.5节参数定义：
    - filter_name: 进程名称过滤（可选）
    - filter_pid: PID过滤（可选）
    - sort_by: 排序字段（可选），默认pid
    - descending: 降序排序（可选），默认False
    - max_results: 最大返回数（可选），默认100
    
    【2026-05-17 小沈】修正S1: 删除limit参数(与max_results重复)
    
    Returns:
        {code, data, message}
    """
    # ⚠️ 警告: 以下参数已从Schema移除，硬编码默认值，后续视需求决定是否恢复
    status: Optional[str] = None
    descending: bool = False
    try:
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'exe', 'cmdline', 'status', 'create_time', 'username']):
            try:
                proc_info = proc.info
                if not _filter_process(proc_info, filter_name, filter_pid, user, status):
                    continue
                processes.append(_format_process(proc_info))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        sort_keys = {
            "pid": lambda x: x["pid"],
            "name": lambda x: x["name"].lower(),
            "cpu": lambda x: x["cpu_percent"],
            "memory": lambda x: x["memory_percent"],
        }
        if sort_by in sort_keys:
            processes.sort(key=sort_keys[sort_by], reverse=descending)
        else:
            processes.sort(key=sort_keys["pid"], reverse=False)

        limited_processes = processes[:max_results]

        return build_success(truncate_data_for_frontend({
                "processes": limited_processes,
                "total": len(limited_processes),
                "total_matched": len(processes),
                "sort_by": sort_by,
            }), f"找到 {len(processes)} 个进程，返回前 {len(limited_processes)} 个", llm_data={
                "总数": len(processes), "返回数": len(limited_processes), "排序": sort_by,
                "进程预览": [{"pid": p.get("pid"), "name": p.get("name","")[:30], "cpu": p.get("cpu_percent"), "mem": p.get("memory_percent")} for p in limited_processes[:20]]
            }, next_actions=build_next_actions([("kill_process", "终止进程", "需要结束某个进程时"), ("get_system_info", "查看系统总览", "需要更多系统信息时")]))

    except Exception as e:
        logger.error(f"[list_processes] 获取进程列表失败: {e}")
        return build_error(ERR_SYSTEM_PROCESS_LIST, f"获取进程列表失败: {str(e)}")


def kill_process(
    pid: int,
    force: bool = False,
    timeout: int = 5,
) -> dict:
    """
    终止指定进程 - 小沈 2026-05-04 修正
    
    按文档参数定义：pid必填，force可选，timeout可选
    
    Args:
        pid: 要终止的进程PID（必填）
        force: 是否强制终止（可选），默认False
        timeout: 等待进程终止的超时时间（秒，可选），默认5秒
    
    Returns:
        {code, data, message}
    """
    # 参数验证
    if pid is None or pid <= 0:
        # 小健 2026-05-19: 修正错误信息(函数无name参数)
        return build_error(ERR_PARAMETER_INVALID, "pid必须为正整数")
    
    try:
        killed_list = []
        
        if pid is not None:
            # 按PID终止单个进程
            proc = psutil.Process(pid)
            
            proc_info = {
                "pid": proc.pid,
                "name": proc.name(),
                "status": proc.status(),
                "exe": proc.exe(),
            }
            
            if force:
                proc.kill()
                terminate_type = "强制终止(SIGKILL)"
            else:
                proc.terminate()
                terminate_type = "正常终止(SIGTERM)"
            
            try:
                proc.wait(timeout=timeout)
                final_status = "已终止"
            except psutil.TimeoutExpired:
                if not force:
                    proc.kill()
                    try:
                        proc.wait(timeout=timeout)
                        final_status = "已强制终止（超时后SIGKILL）"
                    except psutil.TimeoutExpired:
                        final_status = "终止超时，可能需要管理员权限"
                else:
                    final_status = "终止超时，可能需要管理员权限"
            
            killed_list.append({
                "process": proc_info,
                "terminate_type": terminate_type,
                "final_status": final_status,
            })
            
            return build_success({"killed": killed_list}, f"进程 {pid} ({proc_info['name']}) {final_status}", next_actions=build_next_actions([("list_processes", "验证进程已终止", "需要确认终止结果时")]))
        
        # 小健 2026-05-19: 删除按名称批量终止的死代码分支(pid是必填int, else永远不可达, 且引用未定义name变量)
    
    # 【2026-05-17 小沈】修正S6: kill_process幂等化 - NoSuchProcess返回成功而非报错
    except psutil.NoSuchProcess:
        return build_success({"killed": [], "idempotent": True}, f"进程 {pid} 已不存在（幂等：视为已终止）", next_actions=build_next_actions([("list_processes", "验证进程已终止", "需要确认终止结果时")]))
    except psutil.AccessDenied:
        return build_error(ERR_PERMISSION_DENIED, f"无权限终止进程 {pid}，请尝试使用管理员权限")
    except Exception as e:
        logger.error(f"[kill_process] 终止进程失败: {e}")
        return build_error(ERR_SYSTEM_PROCESS_KILL, f"终止进程 {pid} 失败: {str(e)}")


def _log_message(
    message: str,
    level: str = "INFO",
    logger_name: str = "root",
    log_file: Optional[str] = None,
) -> dict:
    """
    记录日志消息到指定日志文件或日志系统 - 按文档7.3节定义
    
    Args:
        message: 日志消息内容（必填）
        level: 日志级别（可选），默认INFO，可选DEBUG/INFO/WARNING/ERROR/CRITICAL
        logger_name: 日志记录器名称（可选），默认root
        log_file: 日志文件路径（可选），默认null输出到控制台
    
    Returns:
        {code, data, message}
    """
    try:
        # 记录日志
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        
        log_level = level_map.get(level.upper(), logging.INFO)
        
        # 使用logger_name创建或获取logger
        log_logger = logging.getLogger(logger_name)
        log_logger.setLevel(log_level)
        
        # 添加控制台处理器（或文件处理器）
        if log_file:
            handler = logging.FileHandler(log_file, encoding="utf-8")
        else:
            handler = logging.StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        log_logger.addHandler(handler)
        
        log_logger.log(log_level, message)
        
        return build_success({
                "level": level,
                "message": message,
                "logger_name": logger_name,
                "log_file": log_file,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }, f"日志记录成功 [{level.upper()}] [{logger_name}] {message}")
    
    except Exception as e:
        return build_error("ERROR", f"记录日志失败: {str(e)}")


def _get_logs(
    log_file: str,
    level: Optional[str] = "WARNING",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    log_format: str = "auto_detect",
    max_lines: int = 200,
    tail_mode: bool = False,
    pattern: Optional[str] = None,
    output_format: str = "table",
) -> dict:
    """
    读取指定日志文件的内容 - 按文档7.3节定义
    
    Args:
        log_file: 日志文件路径（必填）
        level: 日志级别过滤（可选），默认WARNING
        start_time: 起始时间（可选）
        end_time: 结束时间（可选），默认当前
        log_format: 时间格式（可选），默认auto_detect
        max_lines: 最大行数（可选），默认200
        tail_mode: 尾部读取模式（可选），默认false
        pattern: 关键词过滤（可选）
        output_format: 输出格式（可选），默认table
    
    Returns:
        {code, data, message}
    """
    try:
        log_path = Path(log_file)
        
        if not log_path.exists():
            return build_error("ERROR", f"日志文件不存在: {log_file}")
        
        logs = []
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
        
        for line in all_lines:
            line = line.strip()
            if not line:
                continue
            
            # 级别过滤
            if level and level.upper() != "WARNING":
                level_str = f" - {level.upper()} - "
                if level_str not in line and f" - {level.upper()} - " not in line:
                    continue
            
            # pattern过滤
            if pattern and pattern.lower() not in line.lower():
                continue
            
            logs.append(line)
            
            if len(logs) >= max_lines:
                break
        
        # tail_mode处理：直接从末尾读取
        if tail_mode:
            logs = logs[-max_lines:] if len(logs) > max_lines else logs
        
        return build_success({
                "logs": logs,
                "total": len(logs),
                "file": log_file,
                "tail_mode": tail_mode,
            }, f"获取到 {len(logs)} 条日志记录")
    
    except Exception as e:
        logger.error(f"[get_logs] 获取日志失败: {e}")
        return build_error("ERROR", f"获取日志失败: {str(e)}")


def _service_list(
    name: Optional[str] = None,
    state: str = "all",
    output_format: str = "json",
) -> dict:
    """
    列出所有服务 - 小健 2026-05-06 参数名对齐Schema(name/state/output_format)
    
    Windows使用sc query命令，Linux使用systemctl list-units。
    
    Returns:
        {code, data, message}
    """
    filter_name = name
    filter_state = state
    try:
        if platform.system() == "Windows":
            return _windows_service_list(filter_name, filter_state, 100)
        else:
            return _linux_service_list(filter_name, filter_state, 100)
    
    except Exception as e:
        logger.error(f"[service_list] 获取服务列表失败: {e}")
        return build_error(ERR_SERVICE_LIST, f"获取服务列表失败: {str(e)}")


def _filter_services(services: list, filter_name: Optional[str], filter_state: str, max_results: int) -> list:
    """服务过滤 + 截断 — 消除 _windows_service_list 与 _linux_service_list 的 DRY 违规 — 小沈 2026-05-25"""
    filtered = []
    for svc in services:
        if filter_name:
            sn = svc.get("name", "")
            sd = svc.get("display_name", "")
            if filter_name.lower() not in sn.lower() and filter_name.lower() not in sd.lower():
                continue
        if filter_state != "all":
            ss = svc.get("state", "")
            if ss != filter_state:
                continue
        filtered.append(svc)
    return filtered[:max_results]


def _windows_service_list(
    filter_name: Optional[str],
    filter_state: str,
    max_results: int,
) -> dict:
    """Windows服务列表获取"""
    try:
        cmd = ["sc", "query", "type=", "service", "state=", "all"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return build_error(ERR_SERVICE_LIST, f"获取服务列表失败: {result.stderr}")
        
        services = []
        current_service = {}
        
        for line in result.stdout.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("SERVICE_NAME:"):
                if current_service and "name" in current_service:
                    services.append(current_service)
                current_service = {"name": line_stripped.split(":", 1)[1].strip()}
            elif line_stripped.startswith("DISPLAY_NAME:"):
                current_service["display_name"] = line_stripped.split(":", 1)[1].strip()
            elif "STATE" in line and ":" in line:
                state_part = line_stripped.split(":", 1)
                if len(state_part) > 1:
                    state_str = state_part[1].strip()
                    if "RUNNING" in state_str:
                        current_service["state"] = "running"
                    elif "STOPPED" in state_str:
                        current_service["state"] = "stopped"
                    else:
                        current_service["state"] = "other"
                    current_service["state_desc"] = state_str.split()[0] if state_str.split() else state_str
        
        if current_service and "name" in current_service:
            services.append(current_service)
        
        filtered_services = _filter_services(services, filter_name, filter_state, max_results)
        
        return build_success(truncate_data_for_frontend({
                "services": filtered_services,
                "total": len(filtered_services),
                "total_matched": len(services),
                "platform": "Windows",
            }), f"找到 {len(services)} 个服务，返回前 {len(filtered_services)} 个", llm_data={
                "总数": len(services), "返回数": len(filtered_services),
                "服务预览": [{"name": s.get("name","")[:30], "state": s.get("state","")} for s in filtered_services[:20]]
            })
    
    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, "获取服务列表超时")
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "sc命令不存在")


def _linux_service_list(
    filter_name: Optional[str],
    filter_state: str,
    max_results: int,
) -> dict:
    """Linux服务列表获取（systemctl）"""
    try:
        cmd = ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return build_error(ERR_SERVICE_LIST, f"获取服务列表失败: {result.stderr}")
        
        services = []
        lines = result.stdout.splitlines()
        
        for line in lines[1:]:
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) >= 4:
                svc_name = parts[0]
                svc_state = parts[3] if len(parts) > 3 else "unknown"
                
                state_val = "other"
                if svc_state == "running":
                    state_val = "running"
                elif svc_state in ("dead", "exited", "failed"):
                    state_val = "stopped"
                
                services.append({
                    "name": svc_name,
                    "display_name": parts[1] if len(parts) > 1 else svc_name,
                    "state": state_val,
                    "state_desc": svc_state,
                })
        
        filtered_services = _filter_services(services, filter_name, filter_state, max_results)
        
        return build_success(truncate_data_for_frontend({
                "services": filtered_services,
                "total": len(filtered_services),
                "total_matched": len(services),
                "platform": "Linux",
            }), f"找到 {len(services)} 个服务，返回前 {len(filtered_services)} 个", llm_data={
                "总数": len(services), "返回数": len(filtered_services),
                "服务预览": [{"name": s.get("name","")[:30], "state": s.get("state","")} for s in filtered_services[:20]]
            })
    
    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, "获取服务列表超时")
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "systemctl命令不存在")


def _service_start(
    service_name: str,
    wait_for_started: bool = True,
    timeout: int = 30,
) -> dict:
    """
    启动服务 - 小健 2026-05-06 补wait_for_started对齐Schema
    
    Windows使用sc start命令，Linux使用systemctl start。
    
    Args:
        service_name: 要启动的服务名称
        timeout: 等待服务启动的超时时间（秒）
    
    Returns:
        {code, data, message}
    """
    try:
        if platform.system() == "Windows":
            return _windows_service_start(service_name, timeout, wait_for_started)
        else:
            return _linux_service_start(service_name, timeout, wait_for_started)
    
    except Exception as e:
        logger.error(f"[service_start] 启动服务失败: {e}")
        return build_error(ERR_SERVICE_START, f"启动服务失败: {str(e)}")


def _query_sc_service_state(service_name: str) -> str:
    """执行 sc query 并返回归一化状态: running/stopped/unknown — 小沈 2026-05-25"""
    try:
        r = subprocess.run(["sc", "query", service_name], capture_output=True, text=True, timeout=10)
        for line in r.stdout.splitlines():
            s = line.strip()
            if s.startswith("STATE:"):
                if "RUNNING" in s:
                    return "running"
                if "STOPPED" in s:
                    return "stopped"
                return "other"
        return "unknown"
    except Exception:
        return "unknown"


def _wait_sc_service_state(service_name: str, target: str, timeout: int) -> str:
    """轮询等待 Windows 服务达到目标状态，返回最终状态 — 小健 2026-05-25 重构修复other状态"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1)
        state = _query_sc_service_state(service_name)
        if state == target:
            return state
        if state == "other":
            return state
    return _query_sc_service_state(service_name)


def _windows_service_start(service_name: str, timeout: int, wait_for_started: bool = False) -> dict:
    """Windows服务启动 - 小健 2026-05-19 补wait_for_started等待逻辑"""
    try:
        initial = _query_sc_service_state(service_name)
        if initial == "unknown":
            return build_error(ERR_SERVICE_NOT_FOUND, f"服务 {service_name} 不存在")
        if initial == "running":
            return build_success({
                    "service_name": service_name,
                    "state": "running",
                    "action": "none",
                }, f"服务 {service_name} 已经在运行中")

        start_cmd = ["sc", "start", service_name]
        start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=timeout)

        if start_result.returncode != 0:
            return build_error(ERR_SERVICE_START, f"启动服务失败: {start_result.stderr.strip() or start_result.stdout.strip()}")

        if wait_for_started:
            final_state = _wait_sc_service_state(service_name, "running", timeout)
        else:
            time.sleep(2)
            final_state = _query_sc_service_state(service_name)

        return build_success({
                "service_name": service_name,
                "state": final_state,
                "action": "start",
            }, f"服务 {service_name} 启动命令已执行，当前状态: {final_state}")
    
    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, f"启动服务 {service_name} 超时")


def _linux_service_start(service_name: str, timeout: int, wait_for_started: bool = False) -> dict:
    """Linux服务启动 - 小健 2026-05-19 补wait_for_started等待逻辑"""
    try:
        start_cmd = ["systemctl", "start", service_name]
        start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=timeout)
        
        if start_result.returncode != 0:
            return build_error(ERR_SERVICE_START, f"启动服务失败: {start_result.stderr.strip()}")
        
        if wait_for_started:
            deadline = time.time() + timeout
            final_state = "unknown"
            while time.time() < deadline:
                time.sleep(1)
                check_cmd = ["systemctl", "is-active", service_name]
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                final_state = check_result.stdout.strip()
                if final_state == "active":
                    final_state = "running"
                    break
        else:
            check_cmd = ["systemctl", "is-active", service_name]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
            final_state = check_result.stdout.strip()
        
        return build_success({
                "service_name": service_name,
                "state": final_state,
                "action": "start",
            }, f"服务 {service_name} 启动命令已执行，当前状态: {final_state}")
    
    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, f"启动服务 {service_name} 超时")


def _service_stop(
    service_name: str,
    force: bool = False,
    wait_for_stopped: bool = True,
    timeout: int = 30,
) -> dict:
    """
    停止服务 - 小健 2026-05-06 补wait_for_stopped对齐Schema
    
    Windows使用sc stop命令，Linux使用systemctl stop。
    
    Args:
        service_name: 要停止的服务名称
        force: 是否强制停止
        timeout: 等待服务停止的超时时间（秒）
    
    Returns:
        {code, data, message}
    """
    try:
        if platform.system() == "Windows":
            return _windows_service_stop(service_name, force, timeout, wait_for_stopped)
        else:
            return _linux_service_stop(service_name, force, timeout, wait_for_stopped)
    
    except Exception as e:
        logger.error(f"[service_stop] 停止服务失败: {e}")
        return build_error(ERR_SERVICE_STOP, f"停止服务失败: {str(e)}")


def _windows_service_stop(service_name: str, force: bool, timeout: int, wait_for_stopped: bool = False) -> dict:
    """Windows服务停止 - 小健 2026-05-19 补wait_for_stopped等待逻辑"""
    try:
        initial = _query_sc_service_state(service_name)
        if initial == "unknown":
            return build_error(ERR_SERVICE_NOT_FOUND, f"服务 {service_name} 不存在")
        if initial == "stopped":
            return build_success({
                    "service_name": service_name,
                    "state": "stopped",
                    "action": "none",
                }, f"服务 {service_name} 已经停止")

        stop_cmd = ["sc", "stop", service_name]
        stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=timeout)

        if stop_result.returncode != 0:
            if force:
                taskkill_cmd = ["taskkill", "/F", "/IM", f"{service_name}.exe"]
                subprocess.run(taskkill_cmd, capture_output=True, text=True, timeout=10)
            return build_error(ERR_SERVICE_STOP, f"停止服务失败: {stop_result.stderr.strip() or stop_result.stdout.strip()}")

        if wait_for_stopped:
            final_state = _wait_sc_service_state(service_name, "stopped", timeout)
        else:
            time.sleep(2)
            final_state = _query_sc_service_state(service_name)

        stop_type = "强制停止" if force else "优雅停止"
        return build_success({
                "service_name": service_name,
                "state": final_state,
                "action": "stop",
                "stop_type": stop_type,
            }, f"服务 {service_name} 停止命令已执行（{stop_type}），当前状态: {final_state}")

    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, f"停止服务 {service_name} 超时")


def _linux_service_stop(service_name: str, force: bool, timeout: int, wait_for_stopped: bool = False) -> dict:
    """Linux服务停止 - 小健 2026-05-19 补wait_for_stopped等待逻辑"""
    try:
        stop_cmd = ["systemctl", "stop", service_name]
        stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=timeout)
        
        if stop_result.returncode != 0:
            if force:
                kill_cmd = ["systemctl", "kill", service_name]
                subprocess.run(kill_cmd, capture_output=True, text=True, timeout=10)
            
            return build_error(ERR_SERVICE_STOP, f"停止服务失败: {stop_result.stderr.strip()}")
        
        if wait_for_stopped:
            deadline = time.time() + timeout
            final_state = "unknown"
            while time.time() < deadline:
                time.sleep(1)
                check_cmd = ["systemctl", "is-active", service_name]
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                final_state = check_result.stdout.strip()
                if final_state in ("inactive", "failed"):
                    final_state = "stopped"
                    break
        else:
            check_cmd = ["systemctl", "is-active", service_name]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
            final_state = check_result.stdout.strip()
        
        stop_type = "强制停止" if force else "优雅停止"
        
        return build_success({
                "service_name": service_name,
                "state": final_state,
                "action": "stop",
                "stop_type": stop_type,
            }, f"服务 {service_name} 停止命令已执行（{stop_type}），当前状态: {final_state}")
    
    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, f"停止服务 {service_name} 超时")


def _run_schtasks_query() -> str:
    """执行 schtasks /query /fo list /v，返回 stdout 文本。异常由内层抛出

    小沈 2026-05-25 重构拆分
    """
    cmd = ["schtasks", "/query", "/fo", "list", "/v"]
    result = subprocess.run(cmd, capture_output=True, encoding='gbk',
                            errors='ignore', timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"schtasks 执行失败: {result.stderr}")
    if not result.stdout:
        raise ValueError("计划任务列表为空")
    return result.stdout


def _parse_task_entries(stdout: str) -> List[Dict[str, str]]:
    """解析 schtasks /query /fo list /v 输出为结构化 dict 列表。
    可复用于 _task_detail（同样的 schtasks 输出格式）

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
    """过滤 + 截断，返回 (limited, matched_count)

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
    """构建 llm_data 摘要（移除 YAGNI 死代码 _llm["截断"]）

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
    【小沈重构 2026-05-25】重构拆分：提取 _run_schtasks_query / _parse_task_entries / _filter_tasks / _build_task_llm

    使用schtasks query命令列出计划任务。

    Args:
        filter_name: 任务名称过滤（可选）
        filter_status: 状态过滤（ready/running/disabled/all）
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
        }, f"找到 {len(tasks)} 个计划任务，返回前 {len(limited)} 个", llm_data=llm)

    except subprocess.TimeoutExpired:
        return build_error(ERR_SHELL_TIMEOUT, "获取计划任务列表超时")
    except ValueError as e:                    # 小沈 2026-05-25: 恢复ERR_TASK_EMPTY专用错误码
        return build_error(ERR_TASK_EMPTY, str(e))
    except FileNotFoundError:
        return build_error(ERR_SHELL_COMMAND_NOT_FOUND, "schtasks 命令不存在")
    except Exception as e:
        logger.error(f"[task_list] 获取计划任务列表失败: {e}")
        return build_error(ERR_TASK_LIST, f"获取计划任务列表失败: {str(e)}")


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
    """构建 schtasks /create 命令参数列表 — 纯函数，无IO — 小沈 2026-05-25"""
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
        schedule: 计划时间（格式：'HH:MM' 或 'HH:MM /day' 或 'HH:MM /monthly DD'）
        start_time: 起始时间
        start_date: 起始日期
        interval: 重复间隔（分钟）
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

        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=30)

        if result.returncode != 0:
            return build_error(ERR_TASK_CREATE, f"创建计划任务失败: {result.stderr.strip() or result.stdout.strip()}")

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
        return build_error(ERR_TASK_CREATE, f"创建计划任务失败: {str(e)}")


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
        
        # 处理完整的任务名（folder + task_name）
        full_task_name = task_name
        if folder:
            full_task_name = f"{folder}\\{task_name}"
        
        # 先查询确认任务存在
        query_cmd = ["schtasks", "/query", "/tn", full_task_name]
        query_result = subprocess.run(query_cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=10)
        
        if query_result.returncode != 0:
            return build_error(ERR_TASK_NOT_FOUND, f"计划任务 {full_task_name} 不存在")
        
        cmd = ["schtasks", "/delete", "/tn", full_task_name, "/f"]
        
        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=30)
        
        if result.returncode != 0:
            return build_error(ERR_TASK_DELETE, f"删除计划任务失败: {result.stderr.strip() or result.stdout.strip()}")
        
        delete_type = f"强制删除（{folder}）" if folder else "普通删除"
        
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
        return build_error(ERR_TASK_DELETE, f"删除计划任务失败: {str(e)}")


# 【2026-05-17 小沈】统一入口函数：service_control - 合并service_start/service_stop/service_list
def service_control(
    action: Literal["start", "stop", "restart", "list"],
    service_name: Optional[str] = None,
    state: str = "all",
    force: bool = False,
    timeout: int = 30,
) -> dict:
    """
    服务统一控制入口 - 小沈 2026-05-17
    
    通过action参数分发到原service_start/service_stop/service_list实现。
    
    Args:
        action: 操作类型，"start"|"stop"|"restart"|"list"
        service_name: 服务名称（start/stop/restart时必填）
        state: 状态过滤（list时使用），running/stopped/all，默认all
        force: 是否强制停止（stop时使用），默认False
        timeout: 超时秒数（start/stop时使用），默认30
    
    Returns:
        {code, data, message}
    """
    if action == "list":
        result = _service_list(name=service_name, state=state)
    elif action == "start":
        if not service_name:
            return build_error(ERR_PARAMETER_INVALID, "start操作必须提供service_name")
        result = _service_start(service_name=service_name, wait_for_started=False, timeout=timeout)
    elif action == "stop":
        if not service_name:
            return build_error(ERR_PARAMETER_INVALID, "stop操作必须提供service_name")
        result = _service_stop(service_name=service_name, force=force, wait_for_stopped=False, timeout=timeout)
    elif action == "restart":
        if not service_name:
            return build_error(ERR_PARAMETER_INVALID, "restart操作必须提供service_name")
        stop_result = _service_stop(service_name=service_name, force=force, wait_for_stopped=False, timeout=timeout)
        if stop_result.get("code") != "SUCCESS":
            return stop_result
        result = _service_start(service_name=service_name, wait_for_started=False, timeout=timeout)
    else:
        return build_error(ERR_PARAMETER_INVALID, f"不支持的action: {action}，可选: start/stop/restart/list")

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("service_control", "验证服务状态", "需要确认操作结果时", {"action": "list"})])
    return result


# 【2026-05-17 小沈】统一入口函数：task_control - 合并task_create/task_delete/task_list
def task_control(
    action: Literal["create", "delete", "list"],
    task_name: Optional[str] = None,
    command: Optional[str] = None,
    schedule: Optional[str] = None,
    start_time: Optional[str] = None,
    interval: Optional[int] = None,
    state: str = "all",
) -> dict:
    """
    计划任务统一控制入口 - 小沈 2026-05-17
    
    通过action参数分发到原task_create/task_delete/task_list实现。
    
    Args:
        action: 操作类型，"create"|"delete"|"list"
        task_name: 任务名称（create/delete时必填）
        command: 执行命令（create时必填）
        schedule: 计划时间（create时必填），格式'HH:MM'或'HH:MM /day N'或'HH:MM /monthly DD'
        start_time: 起始时间（create时可选）
        interval: 重复间隔分钟数（create时可选）
        state: 状态过滤（list时使用），ready/running/disabled/all，默认all
    
    Returns:
        {code, data, message}
    """
    if action == "list":
        result = _task_list(filter_name=task_name, filter_status=state)
    elif action == "create":
        if not task_name or not command or not schedule:
            return build_error(ERR_PARAMETER_INVALID, "create操作必须提供task_name、command、schedule")
        result = _task_create(
            task_name=task_name,
            command=command,
            schedule=schedule,
            start_time=start_time,
            start_date=None,  # 已从Schema移除，硬编码为None
            interval=interval,
        )
    elif action == "delete":
        if not task_name:
            return build_error(ERR_PARAMETER_INVALID, "delete操作必须提供task_name")
        result = _task_delete(task_name=task_name, folder=None)  # folder已从Schema移除，硬编码为None
    else:
        return build_error(ERR_PARAMETER_INVALID, f"不支持的action: {action}，可选: create/delete/list")

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("task_control", "验证任务状态", "需要确认操作结果时", {"action": "list"})])
    return result
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
