# -*- coding: utf-8 -*-
"""
create_task — 创建Windows计划任务
【2026-06-22 小健】从 system_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import platform
import subprocess
import time as _time_mod
from typing import Dict, Any, Optional

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import TOOL_TIMEOUTS
from app.constants import (
    ERR_DESKTOP_PLATFORM_NOT_SUPPORTED,
    ERR_SHELL_COMMAND_NOT_FOUND,
    ERR_SHELL_TIMEOUT,
    ERR_TASK_CREATE,
)


def _build_schtasks_create_cmd(task_name: str, command: str, schedule: str,
                               description: Optional[str] = None, user: Optional[str] = None,
                               start_time: Optional[str] = None, start_date: Optional[str] = None,
                               interval: Optional[int] = None) -> list:
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


def _build_create_task_llm_data(exec_code: str, duration_ms: int, task_name: str, schedule: str = "",
                                 err_code: str = "", detail: str = "") -> dict:
    """create_task的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"创建计划任务失败: {task_name}",
            "action": {"tool": "create_task", "tool_zh": "创建任务", "target": task_name, "params": {"task_name": task_name, "schedule": schedule}},
            "status": {"exec_code": "error", "message": "创建计划任务失败", "code": err_code or ERR_TASK_CREATE, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"计划任务 {task_name} 创建成功",
        "action": {"tool": "create_task", "tool_zh": "创建任务", "target": task_name, "params": {"task_name": task_name, "schedule": schedule}},
        "status": {"exec_code": "success", "message": "创建计划任务成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def create_task(task_name: str, command: str, schedule: str, interval: Optional[int] = None) -> dict:
    """创建Windows计划任务 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_DESKTOP_PLATFORM_NOT_SUPPORTED)
            return build_error(data={"error_detail": "create_task 仅支持Windows系统", "params": {"platform": platform.system()}}, llm_data=llm_data)

        cmd = _build_schtasks_create_cmd(task_name, command, schedule, None, None, None, None, interval)
        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            err_msg = result.stderr.strip() or result.stdout.strip()
            llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_TASK_CREATE, err_msg)
            return build_error(data={"error_detail": err_msg, "params": {"task_name": task_name, "command": command, "schedule": schedule}}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"task_name": task_name, "command": command, "schedule": schedule}
        llm_data = _build_create_task_llm_data("success", duration_ms, task_name, schedule)
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_SHELL_TIMEOUT)
        return build_error(data={"error_detail": "创建计划任务超时", "params": {"task_name": task_name, "command": command, "schedule": schedule}}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_SHELL_COMMAND_NOT_FOUND)
        return build_error(data={"error_detail": "schtasks命令不存在", "params": {"task_name": task_name}}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[create_task] 创建计划任务失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_TASK_CREATE, str(e))
        return build_error(data={"error_detail": str(e), "params": {"task_name": task_name}}, llm_data=llm_data)


__all__ = ["create_task"]