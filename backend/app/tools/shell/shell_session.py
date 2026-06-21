# -*- coding: utf-8 -*-
"""
S3: shell_session — 后台Shell会话管理

从shell_tools.py拆分而来 — 小欧 2026-06-22
依赖: execute_shell_command._background_shells
"""

import re as _re
import time as _time_mod
from typing import Any, Dict, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.shell.execute_shell_command import _background_shells
from app.tools.toolhelper.shell_helper import _read_stream_nonblocking
from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.tools.tool_constants import SUBPROCESS_TIMEOUT_SHORT, SUBPROCESS_TIMEOUT_VERY_SHORT
from app.constants import (
    ERR_INVALID_ACTION,
    ERR_SHELL_EXEC,
    ERR_SHELL_NOT_FOUND,
)


def _build_shell_session_llm_data(
    exec_code: str, duration_ms: int, shell_id: str = "",
    is_running: bool = False, returncode: int = None,
    terminated: bool = False, err_code: str = "",
    detail: str = "", hint: str = "",
) -> Dict[str, Any]:
    """shell_session的llm_data构建函数 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"Shell会话错误: {shell_id}",
            "action": {"tool": "shell_session", "tool_zh": "Shell会话", "target": shell_id, "params": {"shell_id": shell_id}},
            "status": {"exec_code": "error", "message": detail or "Shell会话错误", "code": err_code or ERR_SHELL_NOT_FOUND, "detail": detail, "hint": hint},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if terminated:
        return {
            "summary": f"会话{shell_id}已终止",
            "action": {"tool": "shell_session", "tool_zh": "Shell会话", "target": shell_id, "params": {"shell_id": shell_id}},
            "status": {"exec_code": "success", "message": "会话已终止", "code": "", "detail": "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    running_text = "运行中" if is_running else "已结束"
    return {
        "summary": f"后台命令输出（{running_text}）",
        "action": {"tool": "shell_session", "tool_zh": "Shell会话", "target": shell_id, "params": {"shell_id": shell_id}},
        "status": {"exec_code": "success", "message": "后台命令输出", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def shell_session(
    shell_id: str,
    action: str = "output",
    filter: Optional[str] = None,
    max_lines: int = 1000,
    force: bool = False,
) -> Dict[str, Any]:
    """后台Shell会话管理 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    if action == "output":
        shell_info = _background_shells.get(shell_id)
        if not shell_info:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_shell_session_llm_data("error", duration_ms, shell_id, err_code=ERR_SHELL_NOT_FOUND, detail="会话不存在")
            return build_error(data={"error_detail": f"后台Shell会话不存在: {shell_id}", "params": {"shell_id": shell_id}}, llm_data=llm_data)
        process = shell_info.get("process")
        if not process:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_shell_session_llm_data("error", duration_ms, shell_id, err_code=ERR_SHELL_NOT_FOUND, detail="会话无进程")
            return build_error(data={"error_detail": f"后台Shell会话无进程: {shell_id}", "params": {"shell_id": shell_id}}, llm_data=llm_data)
        stdout_str = _read_stream_nonblocking(process.stdout, "utf-8")
        stderr_str = _read_stream_nonblocking(process.stderr, "utf-8")
        returncode = process.poll()
        is_running = returncode is None
        if not is_running:
            _background_shells.pop(shell_id, None)
        if filter:
            try:
                pattern = _re.compile(filter)
                stdout_str = "\n".join([l for l in stdout_str.splitlines() if pattern.search(l)])
                stderr_str = "\n".join([l for l in stderr_str.splitlines() if pattern.search(l)])
            except Exception:
                pass
        stdout_lines = stdout_str.splitlines()
        stdout_lines = stdout_lines[-max_lines:]
        stdout_str = "\n".join(stdout_lines)
        resp_data = truncate_data_for_frontend(
            {"shell_id": shell_id, "stdout": stdout_str, "stderr": stderr_str, "is_running": is_running, "returncode": returncode})
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if is_running or returncode == 0:
            llm_data = _build_shell_session_llm_data("success", duration_ms, shell_id, is_running=is_running)
            return build_success(data=resp_data, llm_data=llm_data)
        llm_data = _build_shell_session_llm_data("error", duration_ms, shell_id, is_running=False, returncode=returncode, err_code=ERR_SHELL_EXEC, detail=stderr_str[:200], hint="请检查命令语法")
        return build_error(data=resp_data, llm_data=llm_data)
    elif action == "terminate":
        shell_info = _background_shells.get(shell_id)
        if not shell_info:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_shell_session_llm_data("error", duration_ms, shell_id, err_code=ERR_SHELL_NOT_FOUND, detail="会话不存在")
            return build_error(data={"error_detail": f"后台Shell会话不存在: {shell_id}", "params": {"shell_id": shell_id}}, llm_data=llm_data)
        process = shell_info.get("process")
        if not process:
            _background_shells.pop(shell_id, None)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_shell_session_llm_data("success", duration_ms, shell_id, terminated=True)
            return build_success(data={"shell_id": shell_id, "terminated": True, "force": force, "returncode": None}, llm_data=llm_data)
        terminated = False
        returncode = None
        try:
            if force:
                process.kill()
            else:
                process.terminate()
            process.wait(timeout=SUBPROCESS_TIMEOUT_SHORT)
            terminated = True
            returncode = process.returncode
        except Exception:
            try:
                process.kill()
                process.wait(timeout=SUBPROCESS_TIMEOUT_VERY_SHORT)
                terminated = True
                returncode = process.returncode
            except Exception:
                pass
        _background_shells.pop(shell_id, None)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_shell_session_llm_data("success", duration_ms, shell_id, terminated=terminated)
        return build_success(data={"shell_id": shell_id, "terminated": terminated, "force": force, "returncode": returncode}, llm_data=llm_data)
    else:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_shell_session_llm_data("error", duration_ms, shell_id, err_code=ERR_INVALID_ACTION, detail=f"无效操作: {action}", hint="必须是 output 或 terminate")
        return build_error(data={"error_detail": f"无效的操作类型: {action}", "params": {"action": action}}, llm_data=llm_data)