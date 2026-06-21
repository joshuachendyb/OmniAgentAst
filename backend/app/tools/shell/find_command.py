# -*- coding: utf-8 -*-
"""
S2: find_command — 查找系统命令路径

从shell_tools.py拆分而来 — 小欧 2026-06-22
"""

import os
import shutil
import subprocess
import time as _time_mod
from typing import Any, Dict

from app.tools.tool_response import build_success, build_error
from app.constants import ERR_SHELL_FIND_COMMAND


def _build_find_command_llm_data(
    exec_code: str, duration_ms: int, command: str = "",
    available: bool = False, path: str = "",
    paths: list = None, count: int = 0,
    err_code: str = "", detail: str = "",
) -> Dict[str, Any]:
    """find_command的llm_data构建函数 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"查找命令失败: {command}",
            "action": {"tool": "find_command", "tool_zh": "查找命令", "target": command, "params": {"command": command}},
            "status": {"exec_code": "error", "message": "查找命令失败", "code": err_code or ERR_SHELL_FIND_COMMAND, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if paths is not None:
        return {
            "summary": f"命令 '{command}' 找到 {count} 个路径",
            "action": {"tool": "find_command", "tool_zh": "查找命令", "target": command, "params": {"command": command}},
            "status": {"exec_code": "success", "message": f"找到 {count} 个路径", "code": "", "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {"count": {"value": count, "text": f"{count}个"}},
        }
    status = "可用" if available else "不可用"
    hint = "" if available else "请确认是否已安装并添加到PATH"
    return {
        "summary": f"命令 '{command}' {status}",
        "action": {"tool": "find_command", "tool_zh": "查找命令", "target": command, "params": {"command": command}},
        "status": {"exec_code": "success", "message": f"命令{status}", "code": "", "detail": "", "hint": hint},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def find_command(command: str, all_paths: bool = False) -> Dict[str, Any]:
    """查找系统命令路径 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        if not all_paths:
            cmd_path = shutil.which(command)
            available = cmd_path is not None
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = {"available": available, "command": command, "path": cmd_path}
            llm_data = _build_find_command_llm_data("success", duration_ms, command, available, cmd_path or "")
            return build_success(data=data, llm_data=llm_data)
        else:
            if os.name == 'nt':
                result = subprocess.run(['where', command], capture_output=True, text=True, shell=False)
            else:
                result = subprocess.run(['which', '-a', command], capture_output=True, text=True)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if result.returncode == 0:
                paths = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                data = {"command": command, "paths": paths, "count": len(paths)}
                llm_data = _build_find_command_llm_data("success", duration_ms, command, paths=paths, count=len(paths))
            else:
                data = {"command": command, "paths": [], "count": 0}
                llm_data = _build_find_command_llm_data("success", duration_ms, command, available=False)
            return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_find_command_llm_data("error", duration_ms, command, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"command": command}}, llm_data=llm_data)