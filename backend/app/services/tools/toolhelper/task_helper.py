# -*- coding: utf-8 -*-
"""
Windows计划任务公共Helper - 统一schtasks命令执行和解析

【创建时间】2026-05-18 小沈
【说明】从 system_tools.py 的 task_list/create/delete 提取公共逻辑，
       供 task_control 统一入口内部调用。不注册到tool_registry，不暴露给LLM。

包含函数：
- run_schtasks_command: 统一schtasks命令执行器（默认GBK编码）
- parse_schtasks_query_output: 解析schtasks /query LIST格式输出
- parse_schedule_string: 解析schedule字符串为schtasks参数

Author: 小沈 - 2026-05-18
"""

import subprocess
from typing import Dict, Any, List, Optional, Tuple


def run_schtasks_command(args: List[str], timeout: int = 30) -> Dict[str, Any]:
    """统一schtasks命令执行器 - 小沈 2026-05-18

    schtasks命令输出通常为GBK编码（Windows中文环境），统一处理。

    Args:
        args: schtasks命令参数列表（不含"schtasks"本身）
        timeout: 超时秒数

    Returns:
        {"returncode": int, "stdout": str, "stderr": str}
    """
    cmd = ["schtasks"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
        )
        stdout = result.stdout.decode('gbk', errors='ignore') if isinstance(result.stdout, bytes) else result.stdout
        stderr = result.stderr.decode('gbk', errors='ignore') if isinstance(result.stderr, bytes) else result.stderr
        return {
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"schtasks命令执行超时({timeout}秒)",
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"schtasks命令执行失败: {str(e)}",
        }


def parse_schtasks_query_output(output: str) -> List[Dict[str, str]]:
    """解析schtasks /query /fo LIST格式输出 - 小沈 2026-05-18

    Args:
        output: schtasks /query的stdout输出（LIST格式）

    Returns:
        [{"task_name": ..., "status": ..., "next_run": ..., ...}, ...]
    """
    tasks = []
    current_task: Dict[str, str] = {}

    for line in output.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            if current_task and "task_name" in current_task:
                tasks.append(current_task)
            current_task = {}
            continue

        if ":" in line_stripped:
            key, _, value = line_stripped.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "task name" or key == "任务名":
                current_task["task_name"] = value
            elif key == "status" or key == "状态":
                current_task["status"] = value
            elif key == "next run time" or key == "下次运行时间":
                current_task["next_run"] = value
            elif key == "last run time" or key == "上次运行时间":
                current_task["last_run"] = value
            elif key == "author" or key == "创建者":
                current_task["author"] = value
            elif key == "task to run" or key == "要运行的任务":
                current_task["command"] = value

    if current_task and "task_name" in current_task:
        tasks.append(current_task)

    return tasks


def parse_schedule_string(schedule: str) -> Tuple[str, Dict[str, str]]:
    """解析schedule字符串为schtasks /sc参数 - 小沈 2026-05-18

    Args:
        schedule: 计划字符串，如 "08:00 /day 1" 或 "09:00 /monthly 15"

    Returns:
        (frequency, extra_args)
        frequency: "daily" / "weekly" / "monthly" / "onlogon" / "onstart" / "once"
        extra_args: 额外参数字典
    """
    extra_args: Dict[str, str] = {}
    parts = schedule.strip().split()

    frequency = "daily"
    for part in parts:
        lower = part.lower().lstrip("/")
        if lower in ("day", "daily"):
            frequency = "daily"
        elif lower in ("week", "weekly"):
            frequency = "weekly"
        elif lower in ("month", "monthly"):
            frequency = "monthly"
        elif lower in ("onlogon", "logon"):
            frequency = "onlogon"
        elif lower in ("onstart", "start"):
            frequency = "onstart"
        elif lower in ("once",):
            frequency = "once"
        elif lower.isdigit():
            extra_args["modifier"] = part

    return frequency, extra_args


__all__ = [
    "run_schtasks_command",
    "parse_schtasks_query_output",
    "parse_schedule_string",
]
