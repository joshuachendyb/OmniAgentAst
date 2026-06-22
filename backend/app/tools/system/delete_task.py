# -*- coding: utf-8 -*-
"""
delete_task — 删除Windows计划任务
【2026-06-22 小健】从 system_tools.py 拆分为独立文件
"""

import platform
import subprocess
import time as _time_mod
from typing import Dict, Any

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import TOOL_TIMEOUTS, SUBPROCESS_TIMEOUT_DEFAULT
from app.constants import (
    ERR_DESKTOP_PLATFORM_NOT_SUPPORTED,
    ERR_SHELL_COMMAND_NOT_FOUND,
    ERR_SHELL_TIMEOUT,
    ERR_TASK_DELETE,
    ERR_TASK_NOT_FOUND,
)


def _build_delete_task_llm_data(exec_code: str, duration_ms: int, task_name: str,
                                 err_code: str = "", detail: str = "") -> dict:
    """delete_task的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"删除计划任务失败: {task_name}",
            "action": {"tool": "delete_task", "tool_zh": "删除任务", "target": task_name, "params": {"task_name": task_name}},
            "status": {"exec_code": "error", "message": "删除计划任务失败", "code": err_code or ERR_TASK_DELETE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"计划任务 {task_name} 已删除",
        "action": {"tool": "delete_task", "tool_zh": "删除任务", "target": task_name, "params": {"task_name": task_name}},
        "status": {"exec_code": "success", "message": "删除计划任务成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def delete_task(task_name: str) -> dict:
    """删除Windows计划任务 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_delete_task_llm_data("error", duration_ms, task_name, ERR_DESKTOP_PLATFORM_NOT_SUPPORTED)
            return build_error(data={"error_detail": "delete_task 仅支持Windows系统", "params": {"platform": platform.system()}}, llm_data=llm_data)

        query_cmd = ["schtasks", "/query", "/tn", task_name]
        query_result = subprocess.run(query_cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=SUBPROCESS_TIMEOUT_DEFAULT)

        if query_result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_delete_task_llm_data("error", duration_ms, task_name, ERR_TASK_NOT_FOUND)
            return build_error(data={"error_detail": f"计划任务 {task_name} 不存在", "params": {"name": task_name}}, llm_data=llm_data)

        cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            err_msg = result.stderr.strip() or result.stdout.strip()
            llm_data = _build_delete_task_llm_data("error", duration_ms, task_name, ERR_TASK_DELETE, err_msg)
            return build_error(data={"error_detail": err_msg, "params": {"task_name": task_name}}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"task_name": task_name}
        llm_data = _build_delete_task_llm_data("success", duration_ms, task_name)
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_task_llm_data("error", duration_ms, task_name, ERR_SHELL_TIMEOUT)
        return build_error(data={"error_detail": "删除计划任务超时", "params": {"task_name": task_name}}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_task_llm_data("error", duration_ms, task_name, ERR_SHELL_COMMAND_NOT_FOUND)
        return build_error(data={"error_detail": "schtasks命令不存在", "params": {"task_name": task_name}}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[delete_task] 删除计划任务失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_task_llm_data("error", duration_ms, task_name, ERR_TASK_DELETE, str(e))
        return build_error(data={"error_detail": str(e), "params": {"task_name": task_name}}, llm_data=llm_data)


__all__ = ["delete_task"]