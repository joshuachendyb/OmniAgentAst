# -*- coding: utf-8 -*-
"""
Shell 工具函数模块 - Shell命令执行工具

【创建时间】2026-04-29 小沈
【规范】2026-05-02 小沈 移除 @register_tool 装饰器，改由 shell_register.py 显式注册

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. shell_tools.py: 函数实现（必须有详细注释）
2. shell_schema.py: Pydantic 模型（输入参数定义）
3. shell_register.py: 显式注册（description + examples + input_model）

【2026-05-17 小健】LLM工具: 8→4，降级3个+合并2个
LLM可见工具（4个）：
- execute_shell_command: 执行Shell命令（支持后台运行，cwd参数替代change_directory）
- find_command: 查找命令路径（合并check_command_available+locate_command）
- shell_session: 后台Shell会话管理（合并get_shell_output+terminate_shell）

内部辅助函数（不注册LLM）：
- _get_working_directory: 获取当前工作目录（已降级，execute_shell_command内部使用）
- _check_path_exists: 检查路径是否存在（已降级，内部工具可用）
- _check_shell_injection: Shell注入安全检查
- _read_stream_nonblocking: 非阻塞流读取
- cleanup_background_shells: 批量终止后台Shell

Author: 小沈 - 2026-04-29
"""

import os
import subprocess
import signal
import uuid
import shutil
from typing import Optional, Dict, Any
from datetime import datetime

from app.services.tools.tool_result_utils import format_output_for_llm, build_next_actions, truncate_data_for_frontend
from app.utils.logger import logger  # 小健-2026-05-19 修复BUG-001: logger未导入
from app.services.tools._response import build_success, build_error
from app.services.tools.toolhelper.shell_helper import _check_shell_injection, _read_stream_nonblocking


# 后台Shell会话管理器 - 小沈 2026-05-02
_background_shells: Dict[str, Dict[str, Any]] = {}


def execute_shell_command(
    command: str,
    shell_type: Optional[str] = "powershell",
    timeout: int = 30000,
    run_in_background: bool = False,
    cwd: Optional[str] = None,
    env_vars: Optional[dict] = None,
) -> dict:
    """执行Shell命令 — 小沈 2026-05-19 精简参数(8→6)"""
    # 小健 2026-05-19: shell_type校验 — 非法值明确报错而非静默默认
    if shell_type not in ("powershell", "cmd", None):
        return build_error("ERR_PARAMETER_INVALID", f"shell_type仅支持powershell/cmd，当前值: '{shell_type}'")
    
    # 小健 2026-05-19: command空值校验
    if not command or not command.strip():
        return build_error("ERR_PARAMETER_EMPTY", "command不能为空")
    
    # cwd存在性校验
    if cwd is not None and not os.path.isdir(cwd):
        return build_error("ERR_PARAMETER_INVALID", f"工作目录不存在: {cwd}，请检查路径是否正确")
    
    timeout_sec = timeout / 1000.0
    
    env = None
    if env_vars:
        env = os.environ.copy()
        env.update(env_vars)
    
    if shell_type == "cmd":
        executable = None  # shell=True时使用COMSPEC默认cmd.exe - 小沈 2026-05-06
    else:
        # 【修复 小沈 2026-05-19】动态查找powershell路径，避免硬编码路径失效
        executable = shutil.which("powershell.exe") or shutil.which("pwsh.exe") or "powershell.exe"
    
    try:
        injection_error = _check_shell_injection(command)
        if injection_error:
            logger.warning(f"[Shell安全] 拦截高风险命令: {command[:200]}")
            return build_error("ERR_SHELL_INJECTION", injection_error)
        
        if run_in_background:
            shell_id = f"shell_{uuid.uuid4().hex[:8]}"
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=env,
                executable=executable
            )
            _background_shells[shell_id] = {
                "process": process,
                "command": command,
                "started_at": datetime.now().isoformat(),
                "shell_type": shell_type,
                "cwd": cwd
            }
            return build_success(
                {
                    "shell_id": shell_id,
                    "is_running": True,
                    "started_at": datetime.now().isoformat()
                },
                f"命令已在后台启动，shell_id: {shell_id}",
                next_actions=build_next_actions([
                    ("shell_session", "读取后台命令输出", "需要查看命令执行结果时", {"shell_id": shell_id, "action": "output"}),
                ])
            )
        
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            executable=executable
        )
        timed_out = False
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout_bytes, stderr_bytes = b"", b""
        
        # 手动解码，处理编码问题（先UTF-8，失败后尝试GBK）
        stdout_str = ""
        stderr_str = ""
        try:
            stdout_str = stdout_bytes.decode("utf-8") if stdout_bytes else ""
        except (UnicodeDecodeError, AttributeError):
            stdout_str = stdout_bytes.decode("gbk") if stdout_bytes else ""
        
        try:
            stderr_str = stderr_bytes.decode("utf-8") if stderr_bytes else ""
        except (UnicodeDecodeError, AttributeError):
            stderr_str = stderr_bytes.decode("gbk") if stderr_bytes else ""
        
        returncode = proc.returncode if proc.returncode is not None else -1
        if timed_out:
            return build_error(
                "ERR_SHELL_TIMEOUT",
                f"命令执行超时（{timeout}毫秒），可增大timeout参数重试",
                data={
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "returncode": returncode
                },
                next_actions=build_next_actions([
                    ("execute_shell_command", "增大超时重试", "需要更长时间执行时"),
                ])
            )
        if returncode == 0:
            if stderr_str and stderr_str.strip():
                message = "命令执行成功（有警告输出）"
            else:
                message = "命令执行成功"
            _llm = format_output_for_llm(stdout_str, stderr_str)  # 小沈-2026-05-15
            return build_success(
                truncate_data_for_frontend({
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "returncode": returncode
                }),
                message,
                llm_data=_llm,
                next_actions=build_next_actions([
                    ("execute_shell_command", "继续执行后续命令", "需要执行更多命令时"),
                    ("find_command", "查找命令路径", "需要确认命令是否存在时"),
                ])
            )
        else:
            _llm = format_output_for_llm(stdout_str, stderr_str)
            return build_error(
                "ERR_SHELL_EXEC",
                f"命令执行失败（退出码{returncode}），请检查命令语法和参数",
                data=truncate_data_for_frontend({
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "returncode": returncode
                }),
                llm_data=_llm,
                next_actions=build_next_actions([
                    ("execute_shell_command", "重新执行命令", "修改命令后重试时"),
                    ("find_command", "查找命令路径", "需要确认命令是否存在时"),
                ])
            )
    except Exception as e:
        return build_error("ERR_SHELL_EXCEPTION", f"命令执行异常: {str(e)}")


def _get_working_directory() -> dict:
    """获取当前工作目录（内部辅助函数，不注册LLM）- 小健 2026-05-17 降级自 get_working_directory"""
    try:
        return build_success({"path": os.getcwd()}, "成功获取当前工作目录")
    except Exception as e:
        return build_error("ERR_SHELL_GET_CWD", f"获取工作目录失败: {str(e)}")


def _check_path_exists(path: str) -> dict:
    """检查路径是否存在（内部辅助函数，不注册LLM）- 小健 2026-05-17 降级自 check_path_exists"""
    try:
        exists = os.path.exists(path)
        is_file = os.path.isfile(path) if exists else False
        is_dir = os.path.isdir(path) if exists else False
        return build_success(
            {"exists": exists, "is_file": is_file, "is_directory": is_dir, "path": path},
            "路径存在" if exists else "路径不存在"
        )
    except Exception as e:
        return build_error("ERR_SHELL_CHECK_PATH", f"检查路径失败: {str(e)}")

def find_command(command: str, all_paths: bool = False) -> dict:
    """查找系统命令路径 - 小沈 2026-05-17
    【2026-05-17 小沈】合并 check_command_available + locate_command

    Args:
        command: 要查找的命令名
        all_paths: False=返回第一个匹配路径(快速,shutil.which), True=返回全部匹配路径(完整,where/which -a)

    Returns:
        {code, data, message}
    """
    try:
        if not all_paths:
            cmd_path = shutil.which(command)
            available = cmd_path is not None
            if available:
                return build_success(
                    {"available": True, "command": command, "path": cmd_path},
                    f"命令 '{command}' 可用，路径: {cmd_path}",
                    next_actions=build_next_actions([
                        ("execute_shell_command", "执行该命令", "确认命令可用后需要执行时", {"command": command}),
                    ])
                )
            else:
                return build_success(
                    {"available": False, "command": command, "path": None},
                    f"命令 '{command}' 不可用"
                )
        else:
            if os.name == 'nt':
                result = subprocess.run(
                    ['where', command],
                    capture_output=True,
                    text=True,
                    shell=False
                )
            else:
                result = subprocess.run(
                    ['which', '-a', command],
                    capture_output=True,
                    text=True
                )
            if result.returncode == 0:
                paths = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                return build_success(
                    {"command": command, "paths": paths, "count": len(paths)},
                    f"找到 {len(paths)} 个路径",
                    next_actions=build_next_actions([
                        ("execute_shell_command", "执行该命令", "确认命令可用后需要执行时", {"command": command}),
                    ])
                )
            else:
                return build_success(
                    {"command": command, "paths": [], "count": 0},
                    f"命令 '{command}' 不可用"
                )
    except Exception as e:
        return build_error("ERR_SHELL_FIND_COMMAND", f"查找命令失败: {str(e)}")


def cleanup_background_shells() -> int:
    """终止所有后台shell进程（服务器关闭时调用）- 小健 2026-05-13"""
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
                        process.wait(timeout=3)
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
    """后台Shell会话管理 — 小沈 2026-05-19 精简参数(8→5)"""
    if action == "output":
        shell_info = _background_shells.get(shell_id)
        if not shell_info:
            return build_error("ERR_SHELL_NOT_FOUND", f"后台Shell会话不存在: {shell_id}")
        process = shell_info.get("process")
        if not process:
            return build_error("ERR_SHELL_NOT_FOUND", f"后台Shell会话无进程: {shell_id}")
        stdout_str = _read_stream_nonblocking(process.stdout, "utf-8")
        stderr_str = _read_stream_nonblocking(process.stderr, "utf-8")
        is_running = process.poll() is None
        # 【修复 小沈 2026-05-19】进程已退出时自动清理，防止内存泄漏
        if not is_running:
            _background_shells.pop(shell_id, None)
        if filter:
            import re as _re
            try:
                pattern = _re.compile(filter)
                stdout_lines = [l for l in stdout_str.splitlines() if pattern.search(l)]
                stderr_lines = [l for l in stderr_str.splitlines() if pattern.search(l)]
                stdout_str = "\n".join(stdout_lines)
                stderr_str = "\n".join(stderr_lines)
            except Exception:
                pass
        stdout_lines = stdout_str.splitlines()
        stdout_lines = stdout_lines[-max_lines:]
        stdout_str = "\n".join(stdout_lines)
        return build_success(
            truncate_data_for_frontend({"shell_id": shell_id, "stdout": stdout_str, "stderr": stderr_str, "is_running": is_running}),
            "后台命令输出" if is_running else "后台命令已结束",
            llm_data=format_output_for_llm(stdout_str, stderr_str),
            next_actions=build_next_actions([
                ("shell_session", "继续读取输出", "进程仍在运行需要持续监控时", {"shell_id": shell_id, "action": "output"}),
                ("shell_session", "终止后台命令", "需要停止后台进程或清理会话时", {"shell_id": shell_id, "action": "terminate"}),
            ])  # 小健 2026-05-19: 无论进程是否运行都提供terminate(清理会话防止内存泄漏)
        )
    elif action == "terminate":
        shell_info = _background_shells.get(shell_id)
        if not shell_info:
            return build_error("ERR_SHELL_NOT_FOUND", f"后台Shell会话不存在: {shell_id}")
        process = shell_info.get("process")
        if not process:
            _background_shells.pop(shell_id, None)
            return build_success({"shell_id": shell_id, "terminated": True, "force": force, "returncode": None}, "会话已无进程", next_actions=build_next_actions([
                ("execute_shell_command", "启动新的后台命令", "需要执行新的命令时"),
            ]))
        terminated = False
        returncode = None
        try:
            if force:
                process.kill()
            else:
                process.terminate()
            process.wait(timeout=5)
            terminated = True
            returncode = process.returncode
        except Exception:
            try:
                process.kill()
                process.wait(timeout=3)
                terminated = True
                returncode = process.returncode
            except Exception:
                pass
        _background_shells.pop(shell_id, None)
        return build_success(
            {"shell_id": shell_id, "terminated": terminated, "force": force, "returncode": returncode},
            "已终止后台命令" if terminated else "终止失败",
            next_actions=build_next_actions([
                ("execute_shell_command", "启动新的后台命令", "需要执行新的命令时"),
            ]) if terminated else build_next_actions([
                ("shell_session", "强制终止", "普通终止失败需要强制终止时", {"shell_id": shell_id, "action": "terminate", "force": True}),
            ])
        )
    else:
        return build_error("ERR_INVALID_ACTION", f"无效的操作类型: {action}，必须是 output 或 terminate")
