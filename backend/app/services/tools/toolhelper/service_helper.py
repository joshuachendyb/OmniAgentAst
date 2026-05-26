# -*- coding: utf-8 -*-
"""
Windows服务管理公共Helper - 统一sc命令执行和输出解析

【创建时间】2026-05-18 小沈
【说明】从 system_tools.py 的 _windows_service_list/start/stop 提取公共逻辑，
       供 service_control 统一入口内部调用。不注册到tool_registry，不暴露给LLM。

包含函数：
- run_sc_command: 统一sc命令执行器
- parse_sc_query_state: 从sc query输出解析服务状态
- parse_sc_query_services: 从sc query输出解析服务列表
- check_service_state: 查询单个服务当前状态

Author: 小沈 - 2026-05-18
"""

import subprocess
from typing import Dict, Any, List, Optional


def run_sc_command(args: List[str], timeout: int = 30) -> Dict[str, Any]:
    """统一sc命令执行器 - 小沈 2026-05-18

    Args:
        args: sc命令参数列表（不含"sc"本身），如 ["query", "mysql"]
        timeout: 超时秒数

    Returns:
        {"returncode": int, "stdout": str, "stderr": str}
    """
    cmd = ["sc"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"sc命令执行超时({timeout}秒)",
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"sc命令执行失败: {str(e)}",
        }


def parse_sc_query_state(output: str) -> str:
    """从sc query输出解析服务状态 - 小沈 2026-05-18

    Args:
        output: sc query的stdout输出

    Returns:
        "running" / "stopped" / "other"
    """
    for line in output.splitlines():
        if "STATE" in line and ":" in line:
            state_part = line.strip().split(":", 1)
            if len(state_part) > 1:
                state_desc = state_part[1].strip().lower()
                if "running" in state_desc:
                    return "running"
                elif "stopped" in state_desc:
                    return "stopped"
    return "other"


def parse_sc_query_services(output: str) -> List[Dict[str, str]]:
    """从sc query输出解析服务列表 - 小沈 2026-05-18

    Args:
        output: sc query的stdout输出

    Returns:
        [{"name": ..., "display_name": ..., "state": ..., "state_desc": ...}, ...]
    """
    services = []
    current_service: Dict[str, str] = {}

    for line in output.splitlines():
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
                state_desc = state_part[1].strip()
                current_service["state_desc"] = state_desc
                state_lower = state_desc.lower()
                if "running" in state_lower:
                    current_service["state"] = "running"
                elif "stopped" in state_lower:
                    current_service["state"] = "stopped"
                else:
                    current_service["state"] = "other"

    if current_service and "name" in current_service:
        services.append(current_service)

    return services


def check_service_state(service_name: str, timeout: int = 30) -> Optional[str]:
    """查询单个服务当前状态 - 小沈 2026-05-18

    Args:
        service_name: Windows服务名称
        timeout: 超时秒数

    Returns:
        "running" / "stopped" / "other" / None(查询失败)
    """
    result = run_sc_command(["query", service_name], timeout)
    if result["returncode"] != 0:
        return None
    return parse_sc_query_state(result["stdout"])


__all__ = [
    "run_sc_command",
    "parse_sc_query_state",
    "parse_sc_query_services",
    "check_service_state",
]
