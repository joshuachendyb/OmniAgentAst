# -*- coding: utf-8 -*-
"""
S2: find_command — 查找系统命令路径

从shell_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import os
import shutil
import subprocess
import time as _time_mod
from typing import Any, Dict

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import ERR_SHELL_FIND_COMMAND


def _build_find_command_llm_data(
    exec_code: str, duration_ms: int, command: str = "",
    available: bool = False, path: str = "",
    paths: list = None, count: int = 0,
    err_code: str = "", detail: str = "", all_paths: bool = False,
) -> Dict[str, Any]:
    """find_command的llm_data构建函数 — 小欧 2026-06-22"""
    _act_params = {"command": command, "all_paths": all_paths}
    if exec_code == "error":
        return {
            "summary": f"查找命令失败: {command}",
            "action": {"tool": "which", "tool_zh": "查找命令", "target": command, "params": _act_params},
            "status": {"exec_code": "error", "message": "查找命令失败", "code": err_code or ERR_SHELL_FIND_COMMAND, "detail": detail, "hint": "请检查命令名称是否正确"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        hint = "" if available else "请确认是否已安装并添加到PATH"
        return {
            "summary": f"命令 '{command}' 不可用",
            "action": {"tool": "which", "tool_zh": "查找命令", "target": command, "params": _act_params},
            "status": {"exec_code": "warning", "message": "命令不可用", "code": "", "detail": "", "hint": hint},
            "duration_ms": duration_ms,
            "metrics": {"available": {"value": available, "text": "可用" if available else "不可用"}},
        }
    if paths is not None:
        return {
            "summary": f"命令 '{command}' 找到 {count} 个路径",
            "action": {"tool": "which", "tool_zh": "查找命令", "target": command, "params": _act_params},
            "status": {"exec_code": "success", "message": f"找到 {count} 个路径", "code": "", "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {"count": {"value": count, "text": f"{count}个"}},
        }
    status = "可用" if available else "不可用"
    hint = "" if available else "请确认是否已安装并添加到PATH"
    return {
        "summary": f"命令 '{command}' {status}",
        "action": {"tool": "which", "tool_zh": "查找命令", "target": command, "params": _act_params},
        "status": {"exec_code": "success", "message": f"命令{status}", "code": "", "detail": "", "hint": hint},
        "duration_ms": duration_ms,
        "metrics": {"available": {"value": available, "text": status}},
    }


def which(command: str, all_paths: bool = False) -> Dict[str, Any]:
    """查找系统命令路径 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件 — 小欧 2026-06-24 修复空值校验"""
    t0 = _time_mod.perf_counter()
    if not command or not isinstance(command, str) or not command.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_find_command_llm_data("error", duration_ms, str(command), False, "",
            all_paths=all_paths)
        return build_error(data={"error_detail": "command参数不能为空", "params": {"command": command}}, llm_data=llm_data)
    try:
        if not all_paths:
            cmd_path = shutil.which(command)
            available = cmd_path is not None
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = {"available": available, "command": command, "path": cmd_path}
            if available:
                llm_data = _build_find_command_llm_data("success", duration_ms, command, True, cmd_path or "",
                    all_paths=all_paths)
                # ---- observation_formatter route -------------------------------------------
                # branch: #21 fallback (key:val) — available/path 不命中专用分支
                # trigger: 无上述20条分支匹配
                # handler: _format_scalar_data(data) — key | value 单行列表
                # file:    observation_formatter.py:214
                # ------------------------------------------------------------------------------
                return build_success(data=data, llm_data=llm_data)
            llm_data = _build_find_command_llm_data("warning", duration_ms, command, available=False,
                all_paths=all_paths)
            return build_warning(data=data, llm_data=llm_data)
        else:
            if os.name == 'nt':
                result = subprocess.run(['where', command], capture_output=True, text=True, shell=False, timeout=10)
            else:
                result = subprocess.run(['which', '-a', command], capture_output=True, text=True, timeout=10)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if result.returncode == 0:
                paths = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                data = {"command": command, "paths": paths, "count": len(paths)}
                llm_data = _build_find_command_llm_data("success", duration_ms, command, paths=paths, count=len(paths),
                    all_paths=all_paths)
                # ---- observation_formatter route -------------------------------------------
                # branch: #21 fallback (key:val) — command/paths/count 不命中专用分支
                # trigger: 无上述20条分支匹配
                # handler: _format_scalar_data(data) — key | value 单行列表
                # file:    observation_formatter.py:214
                # ------------------------------------------------------------------------------
                return build_success(data=data, llm_data=llm_data)
            else:
                data = {"command": command, "paths": [], "count": 0}
                llm_data = _build_find_command_llm_data("warning", duration_ms, command, available=False,
                    all_paths=all_paths)
                return build_warning(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_find_command_llm_data("error", duration_ms, command, detail=str(e),
            all_paths=all_paths)
        return build_error(data={"error_detail": str(e), "params": {"command": command}}, llm_data=llm_data)