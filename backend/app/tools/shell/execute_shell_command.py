# -*- coding: utf-8 -*-
"""
S1: execute_shell_command — 执行Shell命令

从shell_tools.py拆分而来 — 小欧 2026-06-22
内聚: _background_shells / _run_shell_background / cleanup_background_shells / _build_shell_result
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import os
import re
import shutil
import subprocess
import threading
import time as _time_mod
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_fc_helper import _decode_bytes_safe
from app.tools.validate.timeout_validator import validate_timeout
from app.services.safety.tool_safety_checker import get_tool_safety_checker
from app.utils.logger import logger
from app.tools.tool_constants import SUBPROCESS_TIMEOUT_SHORT
from app.constants import (
    ERR_PARAMETER_EMPTY,
    ERR_PARAMETER_INVALID,
    ERR_SHELL_EXCEPTION,
    ERR_SHELL_EXEC,
    ERR_SHELL_INJECTION,
    ERR_SHELL_TIMEOUT,
)

_background_shells: Dict[str, Dict[str, Any]] = {}
_background_shells_lock = threading.Lock()

# PowerShell 5.1不支持 && 和 || 作为命令分隔符(仅PS7+支持)
# 翻译规则:
#   cmd1 && cmd2  →  cmd1; if ($?) { cmd2 }       (仅cmd1成功时执行cmd2)
#   cmd1 || cmd2  →  cmd1; if (-not $?) { cmd2 }  (仅cmd1失败时执行cmd2)
_RE_POWERSHELL_AND = re.compile(r'&&\s*')
_RE_POWERSHELL_OR = re.compile(r'\|\|\s*')


def _translate_powershell_operators(command: str) -> str:
    """将 && 和 || 翻译为 PowerShell 5.1 兼容语法 — 小欧 2026-06-25"""
    if '&&' not in command and '||' not in command:
        return command
    # 按优先级：先处理 || 再处理 &&（|| 优先级更低）
    # 简单链式：cmd1 && cmd2 && cmd3 → 逐段处理
    result = command
    # 处理 &&
    while '&&' in result:
        result = _RE_POWERSHELL_AND.sub('; if ($?) { ', result, count=1)
        # 找到对应的闭合 } — 在下一个 && 或 || 或末尾
        marker = '; if ($?) { '
        idx = result.rfind(marker)
        rest = result[idx + len(marker):]
        # 在rest中找到下一个 && 或 || 的位置
        next_op = len(rest)
        for op in ['&&', '||']:
            pos = rest.find(op)
            if pos != -1 and pos < next_op:
                next_op = pos
        # 在 next_op 位置插入 }
        result = result[:idx + len(marker) + next_op] + ' }' + result[idx + len(marker) + next_op:]
    # 处理 ||
    while '||' in result:
        result = _RE_POWERSHELL_OR.sub('; if (-not $?) { ', result, count=1)
        marker = '; if (-not $?) { '
        idx = result.rfind(marker)
        rest = result[idx + len(marker):]
        next_op = len(rest)
        for op in ['&&', '||']:
            pos = rest.find(op)
            if pos != -1 and pos < next_op:
                next_op = pos
        result = result[:idx + len(marker) + next_op] + ' }' + result[idx + len(marker) + next_op:]
    return result


def _build_execute_shell_command_llm_data(
    exec_code: str, duration_ms: int, command: str = "", returncode: int = 0,
    stdout_preview: str = "", stderr_preview: str = "", shell_type: str = "powershell",
    err_code: str = "", detail: str = "",
) -> Dict[str, Any]:
    """execute_shell_command的llm_data构建函数 — 小欧 2026-06-22"""
    cmd_short = (command[:60] + "..." + command[-37:]) if command and len(command) > 100 else (command[:100] if command else "")
    if exec_code == "error":
        _detail = detail or (f"退出码{returncode}" if returncode is not None else "执行异常")
        return {
            "summary": f"执行失败: {_detail}",
            "action": {"tool": "execute_shell_command", "tool_zh": "执行", "target": cmd_short, "params": {"command": cmd_short}},
            "status": {"exec_code": "error", "message": f"执行失败: {detail or (stderr_preview[:200] if stderr_preview else '')}", "code": err_code or ERR_SHELL_EXEC, "detail": detail or (stderr_preview[:200] if stderr_preview else ""), "hint": "请检查命令语法和参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        return {
            "summary": f"执行 {cmd_short}，退出码{returncode}（有警告输出）",
            "action": {"tool": "execute_shell_command", "tool_zh": "执行", "target": cmd_short, "params": {"command": cmd_short}},
            "status": {"exec_code": "warning", "message": "执行成功（有警告输出）", "code": "", "detail": stderr_preview[:200] if stderr_preview else "", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {"exit_code": {"value": returncode, "text": f"退出码{returncode}"}},
        }
    return {
        "summary": f"执行 {cmd_short}，退出码{returncode}",
        "action": {"tool": "execute_shell_command", "tool_zh": "执行", "target": cmd_short, "params": {"command": cmd_short}},
        "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"exit_code": {"value": returncode, "text": f"退出码{returncode}"}},
    }


def _build_shell_result(returncode: int, stdout_str: str, stderr_str: str,
                         timed_out: bool, timeout: int = 60,
                         shell_type: str = "powershell", duration_ms: int = 0) -> Dict[str, Any]:
    """统一构建shell执行结果 — 小欧 2026-06-22
    返回原始字典，不调用build3，不含llm_data — 北京老陈 2026-06-22
    """
    data = {
        "stdout": stdout_str, "stderr": stderr_str,
        "shell_type": shell_type,
        "returncode": returncode,
    }
    if timed_out:
        return {"success": False, "error_detail": f"命令执行超时({timeout}秒)", "data": data, "duration_ms": duration_ms, "params": {"shell_type": shell_type, "timeout": timeout}, "err_code": ERR_SHELL_TIMEOUT}
    if returncode == 0:
        return {"success": True, "data": data, "duration_ms": duration_ms, "params": {"shell_type": shell_type}}
    return {"success": False, "error_detail": f"命令执行失败(退出码{returncode})", "data": data, "duration_ms": duration_ms, "params": {"shell_type": shell_type}}


def _run_shell_background(command: str, executable: Optional[str],
                           cwd: Optional[str], env: Optional[dict],
                           shell_type: str = "powershell") -> Dict[str, Any]:
    """启动后台shell命令 — 小欧 2026-06-22 — 小欧 2026-06-24 修复硬编码shell_type
    返回原始字典，不调用build3，不含llm_data — 北京老陈 2026-06-22
    """
    process = subprocess.Popen(
        command, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=cwd, env=env, executable=executable,
    )
    shell_id = f"shell_{uuid.uuid4().hex[:8]}"
    with _background_shells_lock:
        _background_shells[shell_id] = {
            "process": process, "command": command,
            "started_at": datetime.now().isoformat(),
            "shell_type": shell_type, "cwd": cwd,
        }
    data = {"shell_id": shell_id, "is_running": True, "started_at": datetime.now().isoformat()}
    cmd_short = (command[:60] + "..." + command[-37:]) if command and len(command) > 100 else (command[:100] if command else "")
    return {"success": True, "data": data, "duration_ms": 0, "params": {"shell_type": shell_type}, "command": cmd_short}


def cleanup_background_shells() -> int:
    """终止所有后台shell进程 — 小欧 2026-06-22"""
    from app.tools.tool_constants import SUBPROCESS_TIMEOUT_VERY_SHORT
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


def execute_shell_command(
    command: str, shell_type: Optional[str] = "powershell",
    timeout: int = 60, run_in_background: bool = False,
    cwd: Optional[str] = None,
) -> Dict[str, Any]:
    """执行Shell命令 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件
    包装辅助函数结果，构建build3和llm_data — 北京老陈 2026-06-22
    """
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "execute_shell_command")
    if not timeout_valid:
        llm_data = _build_execute_shell_command_llm_data("error", 0, command, -1, "", "", shell_type or "", ERR_PARAMETER_INVALID, timeout_err)
        return build_error(data={"error_detail": timeout_err, "params": {"timeout": timeout}}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    if shell_type not in ("powershell", "cmd", None):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_shell_command_llm_data("error", duration_ms, command, -1, "", "", shell_type or "", ERR_PARAMETER_INVALID, "shell_type仅支持powershell/cmd")
        return build_error(data={"error_detail": "shell_type仅支持powershell/cmd", "params": {"shell_type": shell_type}}, llm_data=llm_data)
    if not command or not command.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_shell_command_llm_data("error", duration_ms, command, -1, "", "", shell_type or "", ERR_PARAMETER_EMPTY, "command不能为空")
        return build_error(data={"error_detail": "command不能为空", "params": {"command": command}}, llm_data=llm_data)
    if cwd is not None and not os.path.isdir(cwd):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_shell_command_llm_data("error", duration_ms, command, -1, "", "", shell_type or "", ERR_PARAMETER_INVALID, f"工作目录不存在: {cwd}")
        return build_error(data={"error_detail": f"工作目录不存在: {cwd}", "params": {"cwd": cwd}}, llm_data=llm_data)
    if timeout < 1 or timeout > 600:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_shell_command_llm_data("error", duration_ms, command, -1, "", "", shell_type or "", ERR_PARAMETER_INVALID, f"timeout必须在1-600秒之间，当前值: {timeout}")
        return build_error(data={"error_detail": f"timeout必须在1-600秒之间", "params": {"timeout": timeout}}, llm_data=llm_data)

    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'

    executable = None if shell_type == "cmd" else (
        shutil.which("powershell.exe") or shutil.which("pwsh.exe") or "powershell.exe")

    # PowerShell 5.1 不支持 && 和 ||，自动翻译为兼容语法 — 小欧 2026-06-25
    if shell_type == "powershell" and ('&&' in command or '||' in command):
        command = _translate_powershell_operators(command)

    safety_check = get_tool_safety_checker().check_before_execute("execute_shell_command", {"command": command})
    if safety_check.blocked:
        logger.warning(f"[Shell安全] 拦截: {safety_check.message}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_shell_command_llm_data("error", duration_ms, command, -1, "", "", shell_type or "", ERR_SHELL_INJECTION, safety_check.message)
        return build_error(data={"error_detail": safety_check.message, "params": {"command": command[:200]}}, llm_data=llm_data)

    if run_in_background:
        result = _run_shell_background(command, executable, cwd, env)
        # 包装后台命令结果
        duration_ms = result.get("duration_ms", 0)
        data = result.get("data", {})
        command_preview = result.get("command", "")
        llm_data = _build_execute_shell_command_llm_data("success", duration_ms, command_preview, 0, shell_type=shell_type or "powershell")
        llm_data["summary"] = f"后台命令已启动: {command_preview}"
        llm_data["status"]["message"] = "后台命令已启动"
        return build_success(data=data, llm_data=llm_data)

    try:
        proc = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd, env=env, executable=executable)
        timed_out = False
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
            stdout_bytes, stderr_bytes = b"", b""

        stdout_str = _decode_bytes_safe(stdout_bytes)
        stderr_str = _decode_bytes_safe(stderr_bytes)
        returncode = proc.returncode if proc.returncode is not None else -1

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        result = _build_shell_result(returncode, stdout_str, stderr_str, timed_out, timeout=timeout, shell_type=shell_type, duration_ms=duration_ms)
        # 包装结果
        duration_ms = result.get("duration_ms", 0)
        data = result.get("data", {})
        if result.get("success"):
            if stderr_str and stderr_str.strip():
                exec_code = "warning"
            else:
                exec_code = "success"
            llm_data = _build_execute_shell_command_llm_data(exec_code, duration_ms, command[:100], returncode, stdout_str[:200], stderr_str[:200], shell_type or "powershell")
            if exec_code == "warning":
                return build_warning(data=data, llm_data=llm_data)
            return build_success(data=data, llm_data=llm_data)
        else:
            error_detail = result.get("error_detail", "")
            err_code = result.get("err_code", ERR_SHELL_EXEC)
            llm_data = _build_execute_shell_command_llm_data("error", duration_ms, command[:100], returncode, stdout_str[:200], stderr_str[:200], shell_type or "powershell", err_code, error_detail)
            if timed_out:
                llm_data["status"]["hint"] = "可增大timeout参数重试"
            return build_error(data=data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_shell_command_llm_data("error", duration_ms, command, -1, "", "", shell_type or "", ERR_SHELL_EXCEPTION, str(e))
        return build_error(data={"error_detail": str(e), "params": {"command": command[:200]}}, llm_data=llm_data)