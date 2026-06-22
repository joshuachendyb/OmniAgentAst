# -*- coding: utf-8 -*-
"""
get_system_info — 获取系统信息
【2026-06-22 小健】从 system/system_tools.py 迁入 fundamental 为独立文件
"""

import platform
import socket
import time as _time_mod
from typing import Dict, Any

import psutil

from app.tools.tool_response import build_success, build_error
from app.utils.logger import logger
from app.constants import ERR_SYSTEM_INFO


def _build_get_system_info_llm_data(exec_code: str, duration_ms: int, info_type: str) -> dict:
    """get_system_info的llm_data构建函数 — 小健 2026-06-22"""
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


def get_system_info(info_type: str = "all") -> Dict[str, Any]:
    """获取系统信息 — 小健 2026-06-22 迁入fundamental独立文件"""
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
        llm_data = _build_get_system_info_llm_data("success", duration_ms, info_type)
        return build_success(data=data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"[get_system_info] 获取系统信息失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_get_system_info_llm_data("error", duration_ms, info_type)
        return build_error(data={"error_detail": str(e), "params": {"info_type": info_type}}, llm_data=llm_data)


__all__ = ["get_system_info"]