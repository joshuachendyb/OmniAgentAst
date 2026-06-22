# -*- coding: utf-8 -*-
"""
list_tasks — 列出Windows计划任务
【2026-06-22 小健】从 system_tools.py 拆分为独立文件
"""

import platform
import subprocess
import time as _time_mod
from typing import Dict, Any, List, Optional, Tuple

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import TOOL_TIMEOUTS
from app.constants import (
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
    """解析 schtasks /query /fo list /v 输出为结构化 dict 列表 — 小沈 2026-05-25"""
    tasks, current = [], {}
    for line in stdout.splitlines():
        s = line.strip()
        if s.startswith("TaskName:"):
            if current and "name" in current:
                tasks.append(current)
            current = {"name": s.split(":", 1)[1].strip()}
        elif s.startswith("Next Run Time:"):
            current["next_run"] = s.split(":", 1)[1].strip()
        elif s.startswith("Status:"):
            raw = s.split(":", 1)[1].strip()
            current["status"] = {"Ready": "ready", "Running": "running", "Disabled": "disabled"}.get(raw, "other")
            current["status_desc"] = raw
        elif s.startswith("Task To Run:"):
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


def _build_list_tasks_llm_data(exec_code: str, duration_ms: int, tasks: List[Dict], total_raw: int, total_matched: int) -> dict:
    """list_tasks的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": "获取计划任务列表失败",
            "action": {"tool": "list_tasks", "tool_zh": "列出任务", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "获取计划任务列表失败", "code": ERR_TASK_LIST, "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"共 {total_raw} 个计划任务，匹配 {total_matched} 个，返回 {len(tasks)} 个",
        "action": {"tool": "list_tasks", "tool_zh": "列出任务", "target": "", "params": {}},
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
            llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0)
            llm_data["status"]["code"] = ERR_DESKTOP_PLATFORM_NOT_SUPPORTED
            return build_error(data={"error_detail": "list_tasks 仅支持Windows系统", "params": {"platform": platform.system()}}, llm_data=llm_data)

        stdout = _run_schtasks_query()
        tasks = _parse_task_entries(stdout)
        limited, matched = _filter_tasks(tasks, task_name, state, 100)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"tasks": limited, "total": len(limited), "total_matched": len(tasks), "platform": "Windows"}
        llm_data = _build_list_tasks_llm_data("success", duration_ms, limited, len(tasks), matched)
        return build_success(data=data, llm_data=llm_data)

    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0)
        llm_data["status"]["code"] = ERR_SHELL_TIMEOUT
        return build_error(data={"error_detail": "获取计划任务列表超时", "params": {"task_name": task_name, "state": state}}, llm_data=llm_data)
    except ValueError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0)
        llm_data["status"]["code"] = ERR_TASK_EMPTY
        return build_error(data={"error_detail": str(e), "params": {"task_name": task_name}}, llm_data=llm_data)
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0)
        llm_data["status"]["code"] = ERR_SHELL_COMMAND_NOT_FOUND
        return build_error(data={"error_detail": "schtasks 命令不存在", "params": {"task_name": task_name}}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[list_tasks] 获取计划任务列表失败: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_tasks_llm_data("error", duration_ms, [], 0, 0)
        return build_error(data={"error_detail": str(e), "params": {"task_name": task_name}}, llm_data=llm_data)


__all__ = ["list_tasks"]