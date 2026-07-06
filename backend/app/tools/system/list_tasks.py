# -*- coding: utf-8 -*-
"""
list_tasks — 列出Windows计划任务
【2026-06-22 小健】从 system_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import platform
import subprocess
import time as _time_mod
from typing import Dict, Any, List, Optional, Tuple

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import TOOL_TIMEOUTS
from app.tools.tool_constants import (
    ERR_DESKTOP_PLATFORM_NOT_SUPPORTED,
    ERR_SHELL_COMMAND_NOT_FOUND,
    ERR_SHELL_TIMEOUT,
    ERR_TASK_EMPTY,
    ERR_TASK_LIST,
)


def _run_schtasks_query() -> str:
    """执行 schtasks /query /fo list /v,返回 stdout 文本 — 小沈 2026-05-25"""
    cmd = ["schtasks", "/query", "/fo", "list", "/v"]
    result = subprocess.run(cmd, capture_output=True, encoding='gbk', errors='ignore', timeout=TOOL_TIMEOUTS.get("task_control", TOOL_TIMEOUTS["default"]))
    if result.returncode != 0:
        raise RuntimeError(f"schtasks 执行失败: {result.stderr}")
    if not result.stdout:
        raise ValueError("计划任务列表为空")
    return result.stdout


def _parse_task_entries(stdout: str) -> List[Dict[str, str]]:
    """解析 schtasks /query /fo list /v 输出为结构化 dict 列表 — 小沈 2026-05-25 — 小欧 2026-06-24 修复中英文locale兼容"""
    tasks, current = [], {}
    task_name_prefixes = ("TaskName:", "任务名:")
    next_run_prefixes = ("Next Run Time:", "下次运行时间:")
    status_prefixes = ("Status:", "状态:")
    cmd_prefixes = ("Task To Run:", "要运行的任务:")
    for line in stdout.splitlines():
        s = line.strip()
        if any(s.startswith(p) for p in task_name_prefixes):
            if current and "name" in current:
                tasks.append(current)
            current = {"name": s.split(":", 1)[1].strip()}
        elif any(s.startswith(p) for p in next_run_prefixes):
            current["next_run"] = s.split(":", 1)[1].strip()
        elif any(s.startswith(p) for p in status_prefixes):
            raw = s.split(":", 1)[1].strip()
            current["status"] = {"Ready": "ready", "Running": "running", "Disabled": "disabled",
                                 "就绪": "ready", "正在运行": "running", "已禁用": "disabled"}.get(raw, "other")
            current["status_desc"] = raw
        elif any(s.startswith(p) for p in cmd_prefixes):
            current["command"] = s.split(":", 1)[1].strip()
    if current and "name" in current:
        tasks.append(current)
    return tasks


def _filter_tasks(tasks: List[Dict], filter_name: Optional[str], filter_status: str, max_results: int) -> Tuple[List[Dict], int]:
    """过滤 + 截断,返回 (limited, matched_count) — 小沈 2026-05-25"""
    matched = []
    for t in tasks:
        if filter_name and filter_name.lower() not in t.get("name", "").lower():
            continue
        if filter_status != "all" and t.get("status", "") != filter_status:
            continue
        matched.append(t)
    return matched[:max_results], len(matched)


def _build_list_tasks_llm_data(exec_code: str, duration_ms: int, tasks: List[Dict], total_raw: int, total_matched: int,
                               detail: str = "", hint: str = "", task_name: str = "", state: str = "all",
                               err_code: str = "") -> dict:
    """list_tasks的llm_data构建函数 — 小健 2026-06-22 — 小沈 2026-07-05 新增detail/hint/params — 小欧 2026-07-05 加err_code+条件_params"""
    _params = {"state": state}
    if task_name:
        _params["task_name"] = task_name
    if exec_code == "error":
        return {
            "summary": f"获取计划任务列表失败: {detail}",
            "action": {"tool": "list_tasks", "tool_zh": "列出任务", "target": "", "params": _params},
            "status": {"exec_code": "error", "message": detail if detail else "获取计划任务列表失败", "code": err_code or ERR_TASK_LIST, "detail": detail, "hint": hint if hint else "请检查任务名称和系统设置"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"共 {total_raw} 个计划任务，匹配 {total_matched} 个，返回 {len(tasks)} 个",
        "action": {"tool": "list_tasks", "tool_zh": "列出任务", "target": "", "params": _params},
        "status": {"exec_code": "success", "message": "获取计划任务列表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"total": {"value": total_raw, "text": f"{total_raw}个"}, "matched": {"value": total_matched, "text": f"{total_matched}个"}},
    }


def list_tasks(task_name: Optional[str] = None, state: str = "all") -> dict:
    """列出Windows计划任务 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        if platform.system() != "Windows":
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0, detail="list_tasks仅支持Windows系统", hint="当前系统不是Windows", task_name=task_name or "", state=state, err_code=ERR_DESKTOP_PLATFORM_NOT_SUPPORTED)
            return build_error(data={"error_detail": "list_tasks 仅支持Windows系统", "params": {"platform": platform.system()}}, llm_data=llm_data)

        stdout = _run_schtasks_query()
        tasks = _parse_task_entries(stdout)
        limited, matched = _filter_tasks(tasks, task_name, state, 100)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"tasks": limited, "total": len(tasks), "returned": len(limited)}
        llm_data = _build_list_tasks_llm_data("success", duration_ms, limited, len(tasks), matched, task_name=task_name or "", state=state)
        # ---- observation_formatter route -------------------------------------------
        # branch: #14 tasks table
        # trigger: "tasks" in data — tasks 是 List[dict]
        # handler: _format_tasks(data)
        # file:    observation_formatter.py:192-194
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0, detail="获取计划任务列表超时", hint="请检查系统任务计划程序服务", task_name=task_name or "", state=state, err_code=ERR_SHELL_TIMEOUT)
        return build_error(data={"error_detail": "获取计划任务列表超时", "params": {"task_name": task_name, "state": state}}, llm_data=llm_data)
    except ValueError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0, detail=str(e), hint="请检查任务名称是否正确", task_name=task_name or "", state=state, err_code=ERR_TASK_EMPTY)
        return build_error(data={"error_detail": str(e), "params": {"task_name": task_name}}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0, detail="schtasks命令不存在", hint="请确认系统支持schtasks命令", task_name=task_name or "", state=state, err_code=ERR_SHELL_COMMAND_NOT_FOUND)
        return build_error(data={"error_detail": "schtasks 命令不存在", "params": {"task_name": task_name}}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[list_tasks] 获取计划任务列表失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0, detail=str(e), hint="请检查系统任务计划程序状态", task_name=task_name or "", state=state, err_code=ERR_TASK_LIST)
        return build_error(data={"error_detail": str(e), "params": {"task_name": task_name}}, llm_data=llm_data)


__all__ = ["list_tasks"]