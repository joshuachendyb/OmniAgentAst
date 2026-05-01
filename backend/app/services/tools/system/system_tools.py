# -*- coding: utf-8 -*-
"""
SYSTEM 工具函数模块 - 系统信息工具

【创建时间】2026-04-29 小沈
【规范】按新规范使用 Pydantic 模型注册

包含：
- get_system_info: 获取系统信息
- net_connections: 获取网络连接列表
- event_log: 获取系统事件日志

返回格式：统一 {code, data, message} 格式

Author: 小沈 - 2026-04-29
"""

import os
import platform
import psutil
import socket
import subprocess
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from app.utils.logger import logger


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
            "message": f"成功获取系统信息 ({info_type})"
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
        conn_kind_map = {
            "inet": "inet",
            "tcp": "inet4",
            "udp": "inet4",
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
            "message": f"找到 {len(results)} 个网络连接"
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
            return _get_windows_event_log(log_name, max_events, level, source, start_time, event_id)
        else:
            return _get_linux_event_log(log_name, max_events, level, source, start_time, event_id)
    
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
    event_id: Optional[List[int]],
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
        
        cmd = [
            "wevtutil", "qe", log_name,
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
            "message": f"找到 {len(filtered_events[:max_events])} 条事件日志"
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
    event_id: Optional[List[int]],
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
            "message": f"找到 {len(events[:max_events])} 条事件日志"
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
