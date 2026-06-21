# -*- coding: utf-8 -*-
"""
Shell 工具函数模块 - Shell命令执行工具
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。

【2026-06-21 小健】Phase 1 builder改造: build_success/error适配新3字段签名

LLM可见工具(3个):
- execute_shell_command: 执行Shell命令
- find_command: 查找命令路径
- shell_session: 后台Shell会话管理

Author: 小沈 - 2026-04-29
"""

import os
import subprocess
import signal
import uuid
import shutil
import time as _time_mod
from typing import Optional, Dict, Any, List
from datetime import datetime
import re as _re

from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.toolhelper.shell_helper import _check_shell_injection, _read_stream_nonblocking
from app.tools.toolhelper.common_helper import _decode_bytes_safe
from app.services.safety.tool_safety_checker import get_tool_safety_checker
from app.tools.tool_constants import (
    SUBPROCESS_TIMEOUT_SHORT, SUBPROCESS_TIMEOUT_VERY_SHORT,
)
from app.constants import (
    ERR_INVALID_ACTION,
    ERR_PARAMETER_EMPTY,
    ERR_PARAMETER_INVALID,
    ERR_SHELL_CHECK_PATH,
    ERR_SHELL_EXCEPTION,
    ERR_SHELL_EXEC,
    ERR_SHELL_FIND_COMMAND,
    ERR_SHELL_GET_CWD,
    ERR_SHELL_INJECTION,
    ERR_SHELL_NOT_FOUND,
    ERR_SHELL_TIMEOUT,
)


_background_shells: Dict[str, Dict[str, Any]] = {}


def _build_shell_llm(exec_code: str, duration_ms: int, command: str, returncode: int, stdout_preview: str, stderr_preview: str, shell_type: str = "powershell") -> dict:
    """shell工具的llm_data构建函数 — 小健 2026-06-21"""
    cmd_short = command[:100] if command else ""
    if exec_code == "error":
        detail = f"退出码{returncode}" if returncode is not None else "执行异常"
        return {
            "summary": f"命令执行失败: {cmd_short}（{detail}）",
            "action": {"tool": "execute_shell_command", "tool_zh": "执行命令", "target": cmd_short, "params": {"command": cmd_short}},
            "status": {"exec_code": "error", "message": f"命令执行失败({detail})", "code": ERR_SHELL_EXEC, "detail": stderr_preview[:200] if stderr_preview else "", "hint": "请检查命令语法和参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    warning = "（有警告输出）" if stderr_preview and stderr_preview.strip() else ""
    return {
        "summary": f"命令执行成功{warning}: {cmd_short}",
        "action": {"tool": "execute_shell_command", "tool_zh": "执行命令", "target": cmd_short, "params": {"command": cmd_short}},
        "status": {"exec_code": "success", "message": f"命令执行成功{warning}", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"returncode": {"value": returncode, "text": f"退出码{returncode}"}},
    }


def _build_shell_result(returncode: int, stdout_str: str, stderr_str: str,
                         timed_out: bool, timeout: int = 30000,
                         shell_type: str = "powershell", duration_ms: int = 0) -> dict:
    """统一构建 shell 执行结果 — 小健 2026-06-21 适配新3字段"""
    data = truncate_data_for_frontend({
        "stdout": stdout_str, "stderr": stderr_str, "returncode": returncode,
    })

    if timed_out:
        llm_data = _build_shell_llm("error", duration_ms, "", returncode, stdout_str[:200], stderr_str[:200], shell_type)
        llm_data["status"]["code"] = ERR_SHELL_TIMEOUT
        llm_data["status"]["message"] = f"命令执行超时({timeout}毫秒)"
        llm_data["status"]["hint"] = "可增大timeout参数重试"
        return build_error(data=data, llm_data=llm_data)
    if returncode == 0:
        llm_data = _build_shell_llm("success", duration_ms, "", returncode, stdout_str[:200], stderr_str[:200], shell_type)
        return build_success(data=data, llm_data=llm_data)
    llm_data = _build_shell_llm("error", duration_ms, "", returncode, stdout_str[:200], stderr_str[:200], shell_type)
    return build_error(data=data, llm_data=llm_data)


def _build_background_shell_llm(command: str, shell_id: str) -> dict:
    """_run_shell_background的llm_data构建函数 — 小健 2026-06-21"""
    return {
        "summary": f"后台命令已启动: {command[:100]}",
        "action": {"tool": "execute_shell_command", "tool_zh": "执行命令", "target": command[:100], "params": {"command": command[:200]}},
        "status": {"exec_code": "success", "message": "后台命令已启动", "code": "", "detail": "", "hint": ""},
        "duration_ms": 0, "metrics": {},
    }


def _build_find_command_llm(exec_code: str, duration_ms: int, command: str,
                             available: bool = False, path: str = "",
                             paths: list = None, count: int = 0) -> dict:
    """find_command的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"查找命令失败: {command}",
            "action": {"tool": "find_command", "tool_zh": "查找命令", "target": command, "params": {"command": command}},
            "status": {"exec_code": "error", "message": "查找命令失败", "code": ERR_SHELL_FIND_COMMAND, "detail": "", "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
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
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_shell_session_llm(exec_code: str, duration_ms: int, shell_id: str,
                              is_running: bool = False, returncode: int = None,
                              terminated: bool = False, err_code: str = "",
                              detail: str = "", hint: str = "") -> dict:
    """shell_session的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"Shell会话错误: {shell_id}",
            "action": {"tool": "shell_session", "tool_zh": "Shell会话", "target": shell_id, "params": {"shell_id": shell_id}},
            "status": {"exec_code": "error", "message": detail or "Shell会话错误", "code": err_code or ERR_SHELL_NOT_FOUND, "detail": detail, "hint": hint},
            "duration_ms": duration_ms, "metrics": {},
        }
    if terminated:
        return {
            "summary": f"会话{shell_id}已终止",
            "action": {"tool": "shell_session", "tool_zh": "Shell会话", "target": shell_id, "params": {"shell_id": shell_id}},
            "status": {"exec_code": "success", "message": "会话已终止", "code": "", "detail": "", "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    running_text = "运行中" if is_running else "已结束"
    return {
        "summary": f"后台命令输出（{running_text}）",
        "action": {"tool": "shell_session", "tool_zh": "Shell会话", "target": shell_id, "params": {"shell_id": shell_id}},
        "status": {"exec_code": "success", "message": "后台命令输出", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_get_working_directory_llm(exec_code: str, duration_ms: int, path: str = "", detail: str = "") -> dict:
    """_get_working_directory的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": "获取工作目录失败",
            "action": {"tool": "_get_working_directory", "tool_zh": "获取目录", "target": "", "params": {}},
            "status": {"exec_code": "error", "message": "获取工作目录失败", "code": ERR_SHELL_GET_CWD, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"当前工作目录: {path}",
        "action": {"tool": "_get_working_directory", "tool_zh": "获取目录", "target": "", "params": {}},
        "status": {"exec_code": "success", "message": "获取工作目录成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_check_path_exists_llm(exec_code: str, duration_ms: int, path: str,
                                   exists: bool = False, detail: str = "") -> dict:
    """_check_path_exists的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"检查路径失败: {path}",
            "action": {"tool": "_check_path_exists", "tool_zh": "检查路径", "target": path, "params": {"path": path}},
            "status": {"exec_code": "error", "message": "检查路径失败", "code": ERR_SHELL_CHECK_PATH, "detail": detail, "hint": ""},
            "duration_ms": duration_ms, "metrics": {},
        }
    status_text = "存在" if exists else "不存在"
    return {
        "summary": f"路径{status_text}: {path}",
        "action": {"tool": "_check_path_exists", "tool_zh": "检查路径", "target": path, "params": {"path": path}},
        "status": {"exec_code": "success", "message": f"路径{status_text}", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _run_shell_background(
    command: str, executable: Optional[str],
    cwd: Optional[str], env: Optional[dict]
) -> dict:
    """启动后台 shell 命令并立即返回 shell_id — 小健 2026-06-21 适配新3字段"""
    process = subprocess.Popen(
        command, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=cwd, env=env, executable=executable,
    )
    shell_id = f"shell_{uuid.uuid4().hex[:8]}"
    _background_shells[shell_id] = {
        "process": process, "command": command,
        "started_at": datetime.now().isoformat(),
        "shell_type": "powershell", "cwd": cwd,
    }
    data = {"shell_id": shell_id, "is_running": True, "started_at": datetime.now().isoformat()}
    llm_data = _build_background_shell_llm(command, shell_id)
    return build_success(data=data, llm_data=llm_data)


def execute_shell_command(
    command: str, shell_type: Optional[str] = "powershell",
    timeout: int = 30000, run_in_background: bool = False,
    cwd: Optional[str] = None,
) -> dict:
    """执行Shell命令 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    if shell_type not in ("powershell", "cmd", None):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_shell_llm("error", duration_ms, command, -1, "", "", shell_type or "")
        llm_data["status"]["code"] = ERR_PARAMETER_INVALID
        return build_error(data={"error_detail": f"shell_type仅支持powershell/cmd", "params": {"shell_type": shell_type}}, llm_data=llm_data)
    if not command or not command.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_shell_llm("error", duration_ms, command, -1, "", "", shell_type or "")
        llm_data["status"]["code"] = ERR_PARAMETER_EMPTY
        return build_error(data={"error_detail": "command不能为空", "params": {"command": command}}, llm_data=llm_data)
    if cwd is not None and not os.path.isdir(cwd):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_shell_llm("error", duration_ms, command, -1, "", "", shell_type or "")
        llm_data["status"]["code"] = ERR_PARAMETER_INVALID
        return build_error(data={"error_detail": f"工作目录不存在: {cwd}", "params": {"cwd": cwd}}, llm_data=llm_data)

    timeout_sec = timeout / 1000.0
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'

    executable = None if shell_type == "cmd" else (
        shutil.which("powershell.exe") or shutil.which("pwsh.exe") or "powershell.exe")

    safety_check = get_tool_safety_checker().check_before_execute("execute_shell_command", {"command": command})
    if safety_check.get("blocked", False):
        logger.warning(f"[Shell安全] 拦截: {safety_check.get('message')}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_shell_llm("error", duration_ms, command, -1, "", "", shell_type or "")
        llm_data["status"]["code"] = ERR_SHELL_INJECTION
        llm_data["status"]["hint"] = safety_check.get("message", "命令不安全")
        return build_error(data={"error_detail": safety_check.get("message", "命令不安全"), "params": {"command": command[:200]}}, llm_data=llm_data)

    if run_in_background:
        return _run_shell_background(command, executable, cwd, env)

    try:
        proc = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd, env=env, executable=executable)
        timed_out = False
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            try: stdout_bytes, stderr_bytes = proc.communicate(timeout=SUBPROCESS_TIMEOUT_SHORT)
            except subprocess.TimeoutExpired: stdout_bytes, stderr_bytes = b"", b""

        stdout_str = _decode_bytes_safe(stdout_bytes)
        stderr_str = _decode_bytes_safe(stderr_bytes)
        returncode = proc.returncode if proc.returncode is not None else -1

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return _build_shell_result(returncode, stdout_str, stderr_str, timed_out, timeout=timeout, shell_type=shell_type, duration_ms=duration_ms)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_shell_llm("error", duration_ms, command, -1, "", "", shell_type or "")
        llm_data["status"]["code"] = ERR_SHELL_EXCEPTION
        return build_error(data={"error_detail": str(e), "params": {"command": command[:200]}}, llm_data=llm_data)


def _get_working_directory() -> dict:
    """获取当前工作目录(内部辅助函数) — 小健 2026-06-21 适配新3字段"""
    try:
        llm_data = _build_get_working_directory_llm("success", 0, os.getcwd())
        return build_success(data={"path": os.getcwd()}, llm_data=llm_data)
    except Exception as e:
        llm_data = _build_get_working_directory_llm("error", 0, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


def _check_path_exists(path: str) -> dict:
    """检查路径是否存在(内部辅助函数) — 小健 2026-06-21 适配新3字段"""
    try:
        exists = os.path.exists(path)
        is_file = os.path.isfile(path) if exists else False
        is_dir = os.path.isdir(path) if exists else False
        llm_data = _build_check_path_exists_llm("success", 0, path, exists)
        return build_success(data={"exists": exists, "is_file": is_file, "is_directory": is_dir, "path": path}, llm_data=llm_data)
    except Exception as e:
        llm_data = _build_check_path_exists_llm("error", 0, path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"path": path}}, llm_data=llm_data)


def find_command(command: str, all_paths: bool = False) -> dict:
    """查找系统命令路径 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        if not all_paths:
            cmd_path = shutil.which(command)
            available = cmd_path is not None
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = {"available": available, "command": command, "path": cmd_path}
            llm_data = _build_find_command_llm("success", duration_ms, command, available, cmd_path or "")
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
                llm_data = _build_find_command_llm("success", duration_ms, command, paths=paths, count=len(paths))
            else:
                data = {"command": command, "paths": [], "count": 0}
                llm_data = _build_find_command_llm("success", duration_ms, command, available=False)
            return build_success(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_find_command_llm("error", duration_ms, command)
        return build_error(data={"error_detail": str(e), "params": {"command": command}}, llm_data=llm_data)


def cleanup_background_shells() -> int:
    """终止所有后台shell进程 — 小健 2026-05-13"""
    count = 0
    shell_ids = list(_background_shells.keys())
    for shell_id in shell_ids:
        try:
            shell_info = _background_shells.get(shell_id)
            if shell_info:
                process = shell_info.get("process")
                if process and process.poll() is None:
                    process.kill()
                    try:
                        process.wait(timeout=SUBPROCESS_TIMEOUT_VERY_SHORT)
                    except subprocess.TimeoutExpired:
                        pass
                del _background_shells[shell_id]
                count += 1
        except Exception:
            pass
    return count


def shell_session(
    shell_id: str,
    action: str = "output",
    filter: Optional[str] = None,
    max_lines: int = 1000,
    force: bool = False,
) -> dict:
    """后台Shell会话管理 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    if action == "output":
        shell_info = _background_shells.get(shell_id)
        if not shell_info:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_shell_session_llm("error", duration_ms, shell_id, err_code=ERR_SHELL_NOT_FOUND, detail="会话不存在")
            return build_error(data={"error_detail": f"后台Shell会话不存在: {shell_id}", "params": {"shell_id": shell_id}}, llm_data=llm_data)
        process = shell_info.get("process")
        if not process:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_shell_session_llm("error", duration_ms, shell_id, err_code=ERR_SHELL_NOT_FOUND, detail="会话无进程")
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
            llm_data = _build_shell_session_llm("success", duration_ms, shell_id, is_running=is_running)
            return build_success(data=resp_data, llm_data=llm_data)
        llm_data = _build_shell_session_llm("error", duration_ms, shell_id, is_running=False, returncode=returncode, err_code=ERR_SHELL_EXEC, detail=stderr_str[:200], hint="请检查命令语法")
        return build_error(data=resp_data, llm_data=llm_data)
    elif action == "terminate":
        shell_info = _background_shells.get(shell_id)
        if not shell_info:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_shell_session_llm("error", duration_ms, shell_id, err_code=ERR_SHELL_NOT_FOUND, detail="会话不存在")
            return build_error(data={"error_detail": f"后台Shell会话不存在: {shell_id}", "params": {"shell_id": shell_id}}, llm_data=llm_data)
        process = shell_info.get("process")
        if not process:
            _background_shells.pop(shell_id, None)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_shell_session_llm("success", duration_ms, shell_id, terminated=True)
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
        llm_data = _build_shell_session_llm("success", duration_ms, shell_id, terminated=terminated)
        return build_success(data={"shell_id": shell_id, "terminated": terminated, "force": force, "returncode": returncode}, llm_data=llm_data)
    else:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_shell_session_llm("error", duration_ms, shell_id, err_code=ERR_INVALID_ACTION, detail=f"无效操作: {action}", hint="必须是 output 或 terminate")
        return build_error(data={"error_detail": f"无效的操作类型: {action}", "params": {"action": action}}, llm_data=llm_data)
