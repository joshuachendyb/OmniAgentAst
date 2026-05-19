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
- log_message: 记录日志消息
- get_logs: 获取应用日志

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
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime, timedelta
from pathlib import Path

from app.utils.logger import logger
from app.services.tools.tool_result_utils import build_next_actions  # 小沈 2026-05-19


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

        return {
            "code": "SUCCESS",
            "data": data,
            "message": f"成功获取系统信息 ({info_type})",
            "next_actions": build_next_actions([("list_processes", "查看进程详情", "需要进一步排查时"), ("net_connections", "查看网络连接", "需要排查网络时")])
        }

    except Exception as e:
        logger.error(f"[get_system_info] 获取系统信息失败: {e}")
        return {
            "code": "ERR_SYSTEM_INFO",
            "data": None,
            "message": f"获取系统信息失败: {str(e)}"
        }


def net_connections(
    kind: str = "inet",
    state: Optional[str] = None,
    resolve_dns: bool = False,
    process_info: bool = False,
    filter_port: Optional[int] = None,
) -> dict:
    """
    获取网络连接列表 - 小沈 2026-05-02
    
    使用psutil获取网络连接信息。
    支持按类型、状态、端口过滤。
    """
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
        
        return {
            "code": "SUCCESS",
            "data": {
                "connections": results,
                "total": len(results),
                "kind": kind,
                "filter_port": filter_port,
            },
            "message": f"找到 {len(results)} 个网络连接",
            "next_actions": build_next_actions([("get_system_info", "查看系统总览", "需要更多系统信息时")])
        }
    
    except psutil.AccessDenied:
        return {
            "code": "ERR_SYSTEM_ACCESS_DENIED",
            "data": None,
            "message": "需要管理员权限获取网络连接信息"
        }
    except Exception as e:
        logger.error(f"[net_connections] 获取网络连接失败: {e}")
        return {
            "code": "ERR_SYSTEM_NET_CONN",
            "data": None,
            "message": f"获取网络连接失败: {str(e)}"
        }


def event_log(
    log_name: str = "System",
    max_events: int = 50,
    level: str = "error",
    source: Optional[str] = None,
    time_range: str = "1h",
    event_id: Optional[List[int]] = None,
) -> dict:
    """
    获取系统事件日志 - 小沈 2026-05-02
    
    Windows使用wevtutil命令，Linux使用journalctl。
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
        return {
            "code": "ERR_SYSTEM_EVENT_LOG",
            "data": None,
            "message": f"获取事件日志失败: {str(e)}"
        }


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
            return {
                "code": "ERR_SYSTEM_EVENT_LOG",
                "data": None,
                "message": f"获取事件日志失败: {result.stderr}"
            }
        
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
        
        return {
            "code": "SUCCESS",
            "data": {
                "log_name": log_name,
                "events": filtered_events[:max_events],
                "total": len(filtered_events[:max_events]),
                "level": level,
            },
            "message": f"找到 {len(filtered_events[:max_events])} 条事件日志",
            "next_actions": build_next_actions([("get_system_info", "查看系统状态", "需要关联系统信息时")])
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_SYSTEM_TIMEOUT",
            "data": None,
            "message": "获取事件日志超时"
        }
    except FileNotFoundError:
        return {
            "code": "ERR_SYSTEM_COMMAND_NOT_FOUND",
            "data": None,
            "message": "wevtutil命令不存在"
        }


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
            return {
                "code": "ERR_SYSTEM_EVENT_LOG",
                "data": None,
                "message": f"获取事件日志失败: {result.stderr}"
            }
        
        import json as json_module
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
        
        return {
            "code": "SUCCESS",
            "data": {
                "log_name": log_name,
                "events": events[:max_events],
                "total": len(events[:max_events]),
                "level": level,
            },
            "message": f"找到 {len(events[:max_events])} 条事件日志",
            "next_actions": build_next_actions([("get_system_info", "查看系统状态", "需要关联系统信息时")])
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_SYSTEM_TIMEOUT",
            "data": None,
            "message": "获取事件日志超时"
        }
    except FileNotFoundError:
        return {
            "code": "ERR_SYSTEM_COMMAND_NOT_FOUND",
            "data": None,
            "message": "journalctl命令不存在"
        }


def list_processes(
    filter_name: Optional[str] = None,
    filter_pid: Optional[int] = None,
    user: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "pid",
    descending: bool = False,
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
    try:
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'exe', 'cmdline', 'status', 'create_time', 'username']):
            try:
                proc_info = proc.info
                
                # 参数过滤
                if filter_name:
                    proc_name = proc_info.get('name', '')
                    if filter_name.lower() not in proc_name.lower():
                        continue
                
                if filter_pid:
                    if proc_info.get('pid') != filter_pid:
                        continue
                
                # 小健 2026-05-19: 补user/status过滤(原标注暂未生效但数据已有)
                if user:
                    proc_user = proc_info.get('username', '') or ''
                    if user.lower() not in proc_user.lower():
                        continue
                
                if status:
                    proc_status = proc_info.get('status', '') or ''
                    if status.lower() not in proc_status.lower():
                        continue
                
                cpu_percent = proc_info.get('cpu_percent') or 0.0
                memory_percent = proc_info.get('memory_percent') or 0.0
                
                processes.append({
                    "pid": proc_info['pid'],
                    "name": proc_info.get('name', 'N/A'),
                    "status": proc_info.get('status', 'N/A'),
                    "user": proc_info.get('username', 'N/A'),
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_percent": round(memory_percent, 2),
                    "exe": proc_info.get('exe', 'N/A'),
                    "cmdline": ' '.join(proc_info.get('cmdline', []))[:200] if proc_info.get('cmdline') else 'N/A',
                })
            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # 排序处理
        sort_keys = {
            "pid": lambda x: x["pid"],
            "name": lambda x: x["name"].lower(),
            "cpu": lambda x: x["cpu_percent"],
            "memory": lambda x: x["memory_percent"],
        }
        
        # 按pid/name/cpu/memory其中一个排序
        if sort_by in sort_keys:
            processes.sort(key=sort_keys[sort_by], reverse=descending)
        else:
            processes.sort(key=sort_keys["pid"], reverse=False)
        
        limited_processes = processes[:max_results]
        
        return {
            "code": "SUCCESS",
            "data": {
                "processes": limited_processes,
                "total": len(limited_processes),
                "total_matched": len(processes),
                "sort_by": sort_by,
            },
            "message": f"找到 {len(processes)} 个进程，返回前 {len(limited_processes)} 个",
            "next_actions": build_next_actions([("kill_process", "终止进程", "需要结束某个进程时"), ("get_system_info", "查看系统总览", "需要更多系统信息时")])
        }
    
    except Exception as e:
        logger.error(f"[list_processes] 获取进程列表失败: {e}")
        return {
            "code": "ERR_SYSTEM_PROCESS_LIST",
            "data": None,
            "message": f"获取进程列表失败: {str(e)}"
        }


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
        return {
            "code": "ERR_INVALID_PARAM",
            "data": None,
            "message": "pid必须为正整数"  # 小健 2026-05-19: 修正错误信息(函数无name参数)
        }
    
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
            
            return {
                "code": "SUCCESS",
                "data": {"killed": killed_list},
                "message": f"进程 {pid} ({proc_info['name']}) {final_status}",
                "next_actions": build_next_actions([("list_processes", "验证进程已终止", "需要确认终止结果时")])
            }
        
        # 小健 2026-05-19: 删除按名称批量终止的死代码分支(pid是必填int, else永远不可达, 且引用未定义name变量)
    
    # 【2026-05-17 小沈】修正S6: kill_process幂等化 - NoSuchProcess返回成功而非报错
    except psutil.NoSuchProcess:
        return {
            "code": "SUCCESS",
            "data": {"killed": [], "idempotent": True},
            "message": f"进程 {pid} 已不存在（幂等：视为已终止）",
            "next_actions": build_next_actions([("list_processes", "验证进程已终止", "需要确认终止结果时")])
        }
    except psutil.AccessDenied:
        return {
            "code": "ERR_PERMISSION_DENIED",
            "data": None,
            "message": f"无权限终止进程 {pid}，请尝试使用管理员权限"
        }
    except Exception as e:
        logger.error(f"[kill_process] 终止进程失败: {e}")
        return {
            "code": "ERR_SYSTEM_PROCESS_KILL",
            "data": None,
            "message": f"终止进程 {pid} 失败: {str(e)}"
        }


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
        
        return {
            "code": "SUCCESS",
            "data": {
                "level": level,
                "message": message,
                "logger_name": logger_name,
                "log_file": log_file,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "message": f"日志记录成功 [{level.upper()}] [{logger_name}] {message}"
        }
    
    except Exception as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"记录日志失败: {str(e)}"
        }


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
    from pathlib import Path
    
    try:
        log_path = Path(log_file)
        
        if not log_path.exists():
            return {
                "code": "ERROR",
                "data": None,
                "message": f"日志文件不存在: {log_file}"
            }
        
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
        
        return {
            "code": "SUCCESS",
            "data": {
                "logs": logs,
                "total": len(logs),
                "file": log_file,
                "tail_mode": tail_mode,
            },
            "message": f"获取到 {len(logs)} 条日志记录"
        }
    
    except Exception as e:
        logger.error(f"[get_logs] 获取日志失败: {e}")
        return {
            "code": "ERROR",
            "data": None,
            "message": f"获取日志失败: {str(e)}"
        }


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
        return {
            "code": "ERR_SERVICE_LIST",
            "data": None,
            "message": f"获取服务列表失败: {str(e)}"
        }


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
            return {
                "code": "ERR_SERVICE_LIST",
                "data": None,
                "message": f"获取服务列表失败: {result.stderr}"
            }
        
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
        
        filtered_services = []
        for svc in services:
            if filter_name:
                svc_name = svc.get("name", "")
                svc_display = svc.get("display_name", "")
                if filter_name.lower() not in svc_name.lower() and filter_name.lower() not in svc_display.lower():
                    continue
            
            if filter_state != "all":
                svc_state = svc.get("state", "")
                if svc_state != filter_state:
                    continue
            
            filtered_services.append(svc)
        
        limited_services = filtered_services[:max_results]
        
        return {
            "code": "SUCCESS",
            "data": {
                "services": limited_services,
                "total": len(limited_services),
                "total_matched": len(filtered_services),
                "platform": "Windows",
            },
            "message": f"找到 {len(filtered_services)} 个服务，返回前 {len(limited_services)} 个"
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_SERVICE_TIMEOUT",
            "data": None,
            "message": "获取服务列表超时"
        }
    except FileNotFoundError:
        return {
            "code": "ERR_SERVICE_COMMAND_NOT_FOUND",
            "data": None,
            "message": "sc命令不存在"
        }


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
            return {
                "code": "ERR_SERVICE_LIST",
                "data": None,
                "message": f"获取服务列表失败: {result.stderr}"
            }
        
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
        
        filtered_services = []
        for svc in services:
            if filter_name:
                svc_name = svc.get("name", "")
                svc_display = svc.get("display_name", "")
                if filter_name.lower() not in svc_name.lower() and filter_name.lower() not in svc_display.lower():
                    continue
            
            if filter_state != "all":
                svc_state = svc.get("state", "")
                if svc_state != filter_state:
                    continue
            
            filtered_services.append(svc)
        
        limited_services = filtered_services[:max_results]
        
        return {
            "code": "SUCCESS",
            "data": {
                "services": limited_services,
                "total": len(limited_services),
                "total_matched": len(filtered_services),
                "platform": "Linux",
            },
            "message": f"找到 {len(filtered_services)} 个服务，返回前 {len(limited_services)} 个"
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_SERVICE_TIMEOUT",
            "data": None,
            "message": "获取服务列表超时"
        }
    except FileNotFoundError:
        return {
            "code": "ERR_SERVICE_COMMAND_NOT_FOUND",
            "data": None,
            "message": "systemctl命令不存在"
        }


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
        return {
            "code": "ERR_SERVICE_START",
            "data": None,
            "message": f"启动服务失败: {str(e)}"
        }


def _windows_service_start(service_name: str, timeout: int, wait_for_started: bool = False) -> dict:
    """Windows服务启动 - 小健 2026-05-19 补wait_for_started等待逻辑"""
    try:
        query_cmd = ["sc", "query", service_name]
        query_result = subprocess.run(query_cmd, capture_output=True, text=True, timeout=10)
        
        if query_result.returncode != 0:
            return {
                "code": "ERR_SERVICE_NOT_FOUND",
                "data": None,
                "message": f"服务 {service_name} 不存在"
            }
        
        current_state = ""
        for line in query_result.stdout.splitlines():
            if line.strip().startswith("STATE:"):
                current_state = line.strip()
                break
        
        if "RUNNING" in current_state:
            return {
                "code": "SUCCESS",
                "data": {
                    "service_name": service_name,
                    "state": "running",
                    "action": "none",
                },
                "message": f"服务 {service_name} 已经在运行中"
            }
        
        start_cmd = ["sc", "start", service_name]
        start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=timeout)
        
        if start_result.returncode != 0:
            return {
                "code": "ERR_SERVICE_START",
                "data": None,
                "message": f"启动服务失败: {start_result.stderr.strip() or start_result.stdout.strip()}"
            }
        
        import time
        if wait_for_started:
            deadline = time.time() + timeout
            final_state = "unknown"
            while time.time() < deadline:
                time.sleep(1)
                check_cmd = ["sc", "query", service_name]
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                for line in check_result.stdout.splitlines():
                    if line.strip().startswith("STATE:"):
                        if "RUNNING" in line:
                            final_state = "running"
                        elif "STOPPED" in line:
                            final_state = "stopped"
                        break
                if final_state == "running":
                    break
        else:
            time.sleep(2)
            check_cmd = ["sc", "query", service_name]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
            
            final_state = "unknown"
            for line in check_result.stdout.splitlines():
                if line.strip().startswith("STATE:"):
                    if "RUNNING" in line:
                        final_state = "running"
                    elif "STOPPED" in line:
                        final_state = "stopped"
                    break
        
        return {
            "code": "SUCCESS",
            "data": {
                "service_name": service_name,
                "state": final_state,
                "action": "start",
            },
            "message": f"服务 {service_name} 启动命令已执行，当前状态: {final_state}"
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_SERVICE_TIMEOUT",
            "data": None,
            "message": f"启动服务 {service_name} 超时"
        }


def _linux_service_start(service_name: str, timeout: int, wait_for_started: bool = False) -> dict:
    """Linux服务启动 - 小健 2026-05-19 补wait_for_started等待逻辑"""
    try:
        start_cmd = ["systemctl", "start", service_name]
        start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=timeout)
        
        if start_result.returncode != 0:
            return {
                "code": "ERR_SERVICE_START",
                "data": None,
                "message": f"启动服务失败: {start_result.stderr.strip()}"
            }
        
        import time
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
        
        return {
            "code": "SUCCESS",
            "data": {
                "service_name": service_name,
                "state": final_state,
                "action": "start",
            },
            "message": f"服务 {service_name} 启动命令已执行，当前状态: {final_state}"
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_SERVICE_TIMEOUT",
            "data": None,
            "message": f"启动服务 {service_name} 超时"
        }


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
        return {
            "code": "ERR_SERVICE_STOP",
            "data": None,
            "message": f"停止服务失败: {str(e)}"
        }


def _windows_service_stop(service_name: str, force: bool, timeout: int, wait_for_stopped: bool = False) -> dict:
    """Windows服务停止 - 小健 2026-05-19 补wait_for_stopped等待逻辑"""
    try:
        query_cmd = ["sc", "query", service_name]
        query_result = subprocess.run(query_cmd, capture_output=True, text=True, timeout=10)
        
        if query_result.returncode != 0:
            return {
                "code": "ERR_SERVICE_NOT_FOUND",
                "data": None,
                "message": f"服务 {service_name} 不存在"
            }
        
        current_state = ""
        for line in query_result.stdout.splitlines():
            if line.strip().startswith("STATE:"):
                current_state = line.strip()
                break
        
        if "STOPPED" in current_state:
            return {
                "code": "SUCCESS",
                "data": {
                    "service_name": service_name,
                    "state": "stopped",
                    "action": "none",
                },
                "message": f"服务 {service_name} 已经停止"
            }
        
        stop_cmd = ["sc", "stop", service_name]
        stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=timeout)
        
        if stop_result.returncode != 0:
            if force:
                taskkill_cmd = ["taskkill", "/F", "/IM", f"{service_name}.exe"]
                subprocess.run(taskkill_cmd, capture_output=True, text=True, timeout=10)
            
            return {
                "code": "ERR_SERVICE_STOP",
                "data": None,
                "message": f"停止服务失败: {stop_result.stderr.strip() or stop_result.stdout.strip()}"
            }
        
        import time
        if wait_for_stopped:
            deadline = time.time() + timeout
            final_state = "unknown"
            while time.time() < deadline:
                time.sleep(1)
                check_cmd = ["sc", "query", service_name]
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                for line in check_result.stdout.splitlines():
                    if line.strip().startswith("STATE:"):
                        if "STOPPED" in line:
                            final_state = "stopped"
                        elif "RUNNING" in line:
                            final_state = "running"
                        break
                if final_state == "stopped":
                    break
        else:
            time.sleep(2)
            check_cmd = ["sc", "query", service_name]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
            
            final_state = "unknown"
            for line in check_result.stdout.splitlines():
                if line.strip().startswith("STATE:"):
                    if "RUNNING" in line:
                        final_state = "running"
                    elif "STOPPED" in line:
                        final_state = "stopped"
                    break
        
        stop_type = "强制停止" if force else "优雅停止"
        
        return {
            "code": "SUCCESS",
            "data": {
                "service_name": service_name,
                "state": final_state,
                "action": "stop",
                "stop_type": stop_type,
            },
            "message": f"服务 {service_name} 停止命令已执行（{stop_type}），当前状态: {final_state}"
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_SERVICE_TIMEOUT",
            "data": None,
            "message": f"停止服务 {service_name} 超时"
        }


def _linux_service_stop(service_name: str, force: bool, timeout: int, wait_for_stopped: bool = False) -> dict:
    """Linux服务停止 - 小健 2026-05-19 补wait_for_stopped等待逻辑"""
    try:
        stop_cmd = ["systemctl", "stop", service_name]
        stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=timeout)
        
        if stop_result.returncode != 0:
            if force:
                kill_cmd = ["systemctl", "kill", service_name]
                subprocess.run(kill_cmd, capture_output=True, text=True, timeout=10)
            
            return {
                "code": "ERR_SERVICE_STOP",
                "data": None,
                "message": f"停止服务失败: {stop_result.stderr.strip()}"
            }
        
        import time
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
        
        return {
            "code": "SUCCESS",
            "data": {
                "service_name": service_name,
                "state": final_state,
                "action": "stop",
                "stop_type": stop_type,
            },
            "message": f"服务 {service_name} 停止命令已执行（{stop_type}），当前状态: {final_state}"
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_SERVICE_TIMEOUT",
            "data": None,
            "message": f"停止服务 {service_name} 超时"
        }


def _task_list(
    filter_name: Optional[str] = None,
    filter_status: str = "all",
    max_results: int = 100,
) -> dict:
    """
    列出所有计划任务 - 小健 2026-05-06 参数名对齐Schema
    
    使用schtasks query命令列出计划任务。
    
    Args:
        folder: 任务文件夹
        state: 状态过滤（ready/running/disabled）
        output_format: 输出格式（json/table）
    
    Returns:
        {code, data, message}
    """
    try:
        if platform.system() != "Windows":
            return {
                "code": "ERR_PLATFORM_NOT_SUPPORTED",
                "data": None,
                "message": "task_list 仅支持Windows系统"
            }
        
        cmd = ["schtasks", "/query", "/fo", "list", "/v"]
        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=30)
        
        if result.returncode != 0:
            return {
                "code": "ERR_TASK_LIST",
                "data": None,
                "message": f"获取计划任务列表失败: {result.stderr}"
            }
        
        if not result.stdout:
            return {
                "code": "ERR_TASK_EMPTY",
                "data": None,
                "message": "计划任务列表为空"
            }
        
        tasks = []
        current_task = {}
        
        for line in result.stdout.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("TaskName:"):
                if current_task and "name" in current_task:
                    tasks.append(current_task)
                current_task = {"name": line_stripped.split(":", 1)[1].strip()}
            elif line_stripped.startswith("Next Run Time:"):
                current_task["next_run"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("Status:"):
                status_str = line_stripped.split(":", 1)[1].strip()
                if "Ready" in status_str:
                    current_task["status"] = "ready"
                elif "Running" in status_str:
                    current_task["status"] = "running"
                elif "Disabled" in status_str:
                    current_task["status"] = "disabled"
                else:
                    current_task["status"] = "other"
                current_task["status_desc"] = status_str
            elif line_stripped.startswith("Task To Run:"):
                current_task["command"] = line_stripped.split(":", 1)[1].strip()
        
        if current_task and "name" in current_task:
            tasks.append(current_task)
        
        filtered_tasks = []
        for task in tasks:
            if filter_name:
                task_name = task.get("name", "")
                if filter_name.lower() not in task_name.lower():
                    continue

            if filter_status != "all":
                task_status = task.get("status", "")
                if task_status != filter_status:
                    continue

            filtered_tasks.append(task)

        # 【修复 小沈 2026-05-15】应用max_results限制，防止LLM上下文爆满
        limited_tasks = filtered_tasks[:max_results]

        # 【优化 小沈 2026-05-15】llm_data精简摘要
        _llm = {
            "任务总数": len(tasks),
            "过滤后": len(filtered_tasks),
            "返回数": len(limited_tasks),
            "任务列表": [{"名称": t.get("name", ""), "状态": t.get("status_desc", t.get("status", ""))} for t in limited_tasks],
        }
        if len(filtered_tasks) > max_results:
            _llm["截断"] = f"共{len(filtered_tasks)}个，仅返回前{max_results}个"

        return {
            "code": "SUCCESS",
            "data": {
                "tasks": limited_tasks,
                "total": len(limited_tasks),
                "total_matched": len(tasks),
                "platform": "Windows",
            },
            "message": f"找到 {len(tasks)} 个计划任务，返回前 {len(limited_tasks)} 个",
            "llm_data": _llm
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_TASK_TIMEOUT",
            "data": None,
            "message": "获取计划任务列表超时"
        }
    except FileNotFoundError:
        return {
            "code": "ERR_TASK_COMMAND_NOT_FOUND",
            "data": None,
            "message": "schtasks命令不存在"
        }
    except Exception as e:
        logger.error(f"[task_list] 获取计划任务列表失败: {e}")
        return {
            "code": "ERR_TASK_LIST",
            "data": None,
            "message": f"获取计划任务列表失败: {str(e)}"
        }


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
            return {
                "code": "ERR_PLATFORM_NOT_SUPPORTED",
                "data": None,
                "message": "task_create 仅支持Windows系统"
            }
        
        cmd = ["schtasks", "/create", "/tn", task_name, "/tr", command]
        
        # 小健 2026-05-19: 修正schedule解析避免重复/sc参数
        schedule_parts = schedule.split()
        time_part = schedule_parts[0]
        
        # 先确定schedule type和对应参数
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
        
        cmd.extend(["/sc", sc_type, "/st", time_part])
        cmd.extend(sc_extra)
        
        if description:
            cmd.extend(["/d", description])
        
        if user:
            cmd.extend(["/ru", user])
        
        if start_time:
            cmd.extend(["/st", start_time])  # 小健 2026-05-19: /sd是Start Date, /st才是Start Time
        
        if start_date:
            cmd.extend(["/sd", start_date])  # 小健 2026-05-19: 补充start_date参数(原为死参数)
        
        if interval and interval > 0:
            cmd.extend(["/ri", str(interval)])  # 小健 2026-05-19: 补充interval参数(原为死参数)
        
        cmd.append("/f")
        
        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=30)
        
        if result.returncode != 0:
            return {
                "code": "ERR_TASK_CREATE",
                "data": None,
                "message": f"创建计划任务失败: {result.stderr.strip() or result.stdout.strip()}"
            }
        
        return {
            "code": "SUCCESS",
            "data": {
                "task_name": task_name,
                "command": command,
                "schedule": schedule,
                "description": description,
                "user": user,
            },
            "message": f"计划任务 {task_name} 创建成功"
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_TASK_TIMEOUT",
            "data": None,
            "message": "创建计划任务超时"
        }
    except FileNotFoundError:
        return {
            "code": "ERR_TASK_COMMAND_NOT_FOUND",
            "data": None,
            "message": "schtasks命令不存在"
        }
    except Exception as e:
        logger.error(f"[task_create] 创建计划任务失败: {e}")
        return {
            "code": "ERR_TASK_CREATE",
            "data": None,
            "message": f"创建计划任务失败: {str(e)}"
        }


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
            return {
                "code": "ERR_PLATFORM_NOT_SUPPORTED",
                "data": None,
                "message": "task_delete 仅支持Windows系统"
            }
        
        # 处理完整的任务名（folder + task_name）
        full_task_name = task_name
        if folder:
            full_task_name = f"{folder}\\{task_name}"
        
        # 先查询确认任务存在
        query_cmd = ["schtasks", "/query", "/tn", full_task_name]
        query_result = subprocess.run(query_cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=10)
        
        if query_result.returncode != 0:
            return {
                "code": "ERR_TASK_NOT_FOUND",
                "data": None,
                "message": f"计划任务 {full_task_name} 不存在"
            }
        
        cmd = ["schtasks", "/delete", "/tn", full_task_name, "/f"]
        
        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=30)
        
        if result.returncode != 0:
            return {
                "code": "ERR_TASK_DELETE",
                "data": None,
                "message": f"删除计划任务失败: {result.stderr.strip() or result.stdout.strip()}"
            }
        
        delete_type = f"强制删除（{folder}）" if folder else "普通删除"
        
        return {
            "code": "SUCCESS",
            "data": {
                "task_name": full_task_name,
                "folder": folder,
                "delete_type": delete_type,
            },
            "message": f"计划任务 {full_task_name} 已删除"
        }
    
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_TASK_TIMEOUT",
            "data": None,
            "message": "删除计划任务超时"
        }
    except FileNotFoundError:
        return {
            "code": "ERR_TASK_COMMAND_NOT_FOUND",
            "data": None,
            "message": "schtasks命令不存在"
        }
    except Exception as e:
        logger.error(f"[task_delete] 删除计划任务失败: {e}")
        return {
            "code": "ERR_TASK_DELETE",
            "data": None,
            "message": f"删除计划任务失败: {str(e)}"
        }


# 【2026-05-17 小沈】统一入口函数：service_control - 合并service_start/service_stop/service_list
def service_control(
    action: Literal["start", "stop", "restart", "list"],
    service_name: Optional[str] = None,
    state: str = "all",
    force: bool = False,
    wait_for_started: bool = False,
    wait_for_stopped: bool = False,
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
        wait_for_started: 等待启动完成（start时使用），默认False
        wait_for_stopped: 等待停止完成（stop时使用），默认False
        timeout: 超时秒数（start/stop时使用），默认30
    
    Returns:
        {code, data, message}
    """
    if action == "list":
        result = _service_list(name=service_name, state=state)
    elif action == "start":
        if not service_name:
            return {"code": "ERR_INVALID_PARAM", "data": None, "message": "start操作必须提供service_name"}
        result = _service_start(service_name=service_name, wait_for_started=wait_for_started, timeout=timeout)
    elif action == "stop":
        if not service_name:
            return {"code": "ERR_INVALID_PARAM", "data": None, "message": "stop操作必须提供service_name"}
        result = _service_stop(service_name=service_name, force=force, wait_for_stopped=wait_for_stopped, timeout=timeout)
    elif action == "restart":
        if not service_name:
            return {"code": "ERR_INVALID_PARAM", "data": None, "message": "restart操作必须提供service_name"}
        stop_result = _service_stop(service_name=service_name, force=force, wait_for_stopped=wait_for_stopped, timeout=timeout)
        if stop_result.get("code") != "SUCCESS":
            return stop_result
        result = _service_start(service_name=service_name, wait_for_started=wait_for_started, timeout=timeout)
    else:
        return {"code": "ERR_INVALID_PARAM", "data": None, "message": f"不支持的action: {action}，可选: start/stop/restart/list"}

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
    start_date: Optional[str] = None,
    interval: Optional[int] = None,
    state: str = "all",
    folder: Optional[str] = None,
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
        start_date: 起始日期（create时可选）
        interval: 重复间隔分钟数（create时可选）
        state: 状态过滤（list时使用），ready/running/disabled/all，默认all
        folder: 任务文件夹（delete时可选）
    
    Returns:
        {code, data, message}
    """
    if action == "list":
        result = _task_list(filter_name=task_name, filter_status=state)
    elif action == "create":
        if not task_name or not command or not schedule:
            return {"code": "ERR_INVALID_PARAM", "data": None, "message": "create操作必须提供task_name、command、schedule"}
        result = _task_create(
            task_name=task_name,
            command=command,
            schedule=schedule,
            start_time=start_time,
            start_date=start_date,
            interval=interval,
        )
    elif action == "delete":
        if not task_name:
            return {"code": "ERR_INVALID_PARAM", "data": None, "message": "delete操作必须提供task_name"}
        result = _task_delete(task_name=task_name, folder=folder)
    else:
        return {"code": "ERR_INVALID_PARAM", "data": None, "message": f"不支持的action: {action}，可选: create/delete/list"}

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("task_control", "验证任务状态", "需要确认操作结果时", {"action": "list"})])
    return result
