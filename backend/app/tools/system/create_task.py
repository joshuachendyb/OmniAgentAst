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
from app.tools.validate.tools_file_path_checker import validate_str_param
from app.tools.tool_constants import (
    ERR_DESKTOP_PLATFORM_NOT_SUPPORTED,
    ERR_SHELL_COMMAND_NOT_FOUND,
    ERR_SHELL_TIMEOUT,
    ERR_TASK_CREATE,
)


def _build_schtasks_create_cmd(task_name: str, command: str, schedule: str,
                               description: Optional[str] = None, user: Optional[str] = None,
                               start_time: Optional[str] = None, start_date: Optional[str] = None,
                               interval: Optional[int] = None) -> list:
    """构建 schtasks /create 命令参数列表 — 纯函数,无IO — 小沈 2026-05-25
    小欧 2026-07-04 修复: 增加schedule空值和day范围校验
    """
    if not isinstance(schedule, str) or not schedule.strip():
        raise ValueError("schedule不能为空")
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
                if day_num.isdigit() and (int(day_num) < 1 or int(day_num) > 7):
                    raise ValueError(f"day值必须在1-7之间，当前值: {day_num}")
                day_name = "MON,TUE,WED,THU,FRI,SAT,SUN".split(",")[int(day_num)-1] if day_num.isdigit() else day_num
                sc_extra = ["/d", day_name]
        elif "/monthly" in schedule_parts:
            monthly_idx = schedule_parts.index("/monthly")
            if monthly_idx + 1 < len(schedule_parts):
                day_num = schedule_parts[monthly_idx + 1]
                sc_type = "monthly"
                sc_extra = ["/d", day_num]

    cmd.extend(sc_extra)
    if start_time:
        cmd.extend(["/st", start_time])
    else:
        cmd.extend(["/st", time_part])
    if user:
        cmd.extend(["/ru", user])
    if start_date:
        cmd.extend(["/sd", start_date])
    if interval and interval > 0:
        cmd.extend(["/ri", str(interval)])

    cmd.append("/f")
    return cmd


def _build_create_task_llm_data(exec_code: str, duration_ms: int, task_name: str, schedule: str = "",
                                 err_code: str = "", detail: str = "", hint: str = "") -> dict:
    """create_task的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增hint"""
    _act_params = {"task_name": task_name}
    if schedule:
        _act_params["schedule"] = schedule
    if exec_code == "error":
        return {
            "summary": f"创建计划任务{task_name}，失败",
            "action": {"tool": "create_task", "tool_zh": "创建任务", "target": task_name, "params": _act_params},
            "status": {"exec_code": "error", "message": "创建计划任务失败", "code": err_code or ERR_TASK_CREATE, "detail": detail, "hint": hint if hint else "请检查任务名称和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"创建计划任务{task_name}，成功",
        "action": {"tool": "create_task", "tool_zh": "创建任务", "target": task_name, "params": _act_params},
        "status": {"exec_code": "success", "message": "创建计划任务成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def create_task(task_name: str, command: str, schedule: str, interval: Optional[int] = None) -> dict:
    """创建Windows计划任务 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    err = validate_str_param(task_name, "task_name")
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm_data("error", duration_ms, task_name, "", ERR_TASK_CREATE, err, hint="请检查任务名称")
        return build_error(data={}, llm_data=llm_data)
    err = validate_str_param(command, "command")
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm_data("error", duration_ms, task_name, "", ERR_TASK_CREATE, err, hint="请检查命令参数")
        return build_error(data={}, llm_data=llm_data)
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_DESKTOP_PLATFORM_NOT_SUPPORTED, hint="当前系统不是Windows")
            return build_error(data={}, llm_data=llm_data)

        cmd = _build_schtasks_create_cmd(task_name, command, schedule, None, None, None, None, interval)
        result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))

        if result.returncode != 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            err_msg = result.stderr.strip() or result.stdout.strip()
            llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_TASK_CREATE, err_msg, hint=f"请检查schtasks命令可用性,任务名: {task_name}")
            return build_error(data={}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {}
        llm_data = _build_create_task_llm_data("success", duration_ms, task_name, schedule)
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val)
        # trigger: 无上述20条分支匹配 — task_name/command/schedule 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_SHELL_TIMEOUT, f"创建计划任务超时: {task_name}", hint="执行schtasks命令超时,请检查系统状态")
        return build_error(data={}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_SHELL_COMMAND_NOT_FOUND, f"schtasks命令不存在,无法创建任务: {task_name}", hint="系统缺少schtasks命令,请确认Windows版本")
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[create_task] 创建计划任务失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_create_task_llm_data("error", duration_ms, task_name, schedule, ERR_TASK_CREATE, str(e), hint=f"创建任务异常,任务名: {task_name}")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["create_task"]