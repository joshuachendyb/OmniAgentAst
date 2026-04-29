# -*- coding: utf-8 -*-
"""
SYSTEM 工具函数模块 - 系统信息工具

【创建时间】2026-04-29 小沈
【规范】按新规范使用 Pydantic 模型注册

包含：
- get_system_info: 获取系统信息

返回格式：统一 {code, data, message} 格式

Author: 小沈 - 2026-04-29
"""

import os
import platform
import psutil
import socket
from typing import Optional, Dict, Any

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
