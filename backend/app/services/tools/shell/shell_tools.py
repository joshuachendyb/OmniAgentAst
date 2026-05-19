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
import re
import uuid
import shutil
from typing import Optional, Dict, Any
from datetime import datetime

from app.services.tools.tool_result_utils import format_output_for_llm, build_next_actions  # 小沈-2026-05-15, 小沈-2026-05-19
from app.utils.logger import logger  # 小健-2026-05-19 修复BUG-001: logger未导入


# 后台Shell会话管理器 - 小沈 2026-05-02
_background_shells: Dict[str, Dict[str, Any]] = {}

# 高风险shell注入模式 - 小健 2026-05-13 补充安全验证
SHELL_INJECTION_PATTERNS = [
    (r'\$\(', '子shell执行 $()'),
    (r'`[^`]*`', '命令替换反引号'),
]

def _check_shell_injection(command: str) -> Optional[str]:
    """检查shell命令注入风险，返回错误描述或None - 小健 2026-05-13"""
    if not command or not command.strip():
        return None
    for pattern, desc in SHELL_INJECTION_PATTERNS:
        if re.search(pattern, command):
            return f"检测到高风险shell注入模式: {desc}"
    return None


def execute_shell_command(
    command: str,
    shell_type: Optional[str] = "powershell",
    timeout: int = 30000,
    run_in_background: bool = False,
    cwd: Optional[str] = None,
    env_vars: Optional[dict] = None,
) -> dict:
    """执行Shell命令 — 小沈 2026-05-19 精简参数(8→6)"""
    encoding = None  # 小沈 2026-05-19: 已从Schema移除，实现自动回退utf-8→gbk
    # 小健 2026-05-19: shell_type校验 — 非法值明确报错而非静默默认
    if shell_type not in ("powershell", "cmd", None):
        return {
            "code": -1,
            "data": None,
            "message": f"shell_type仅支持powershell/cmd，当前值: '{shell_type}'"
        }
    
    # 小健 2026-05-19: command空值校验
    if not command or not command.strip():
        return {
            "code": -1,
            "data": None,
            "message": "command不能为空"
        }
    
    # cwd存在性校验
    if cwd is not None and not os.path.isdir(cwd):
        return {
            "code": -1,
            "data": None,
            "message": f"工作目录不存在: {cwd}"
        }
    
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
    
    # encoding: 使用指定的编码或默认 utf-8
    use_encoding = encoding if encoding else "utf-8"
    
    try:
        injection_error = _check_shell_injection(command)
        if injection_error:
            logger.warning(f"[Shell安全] 拦截高风险命令: {command[:200]}")
            return {
                "code": "ERR_SHELL_INJECTION",
                "data": None,
                "message": injection_error
            }
        
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
            return {
                "code": "SUCCESS",
                "data": {
                    "shell_id": shell_id,
                    "is_running": True,
                    "started_at": datetime.now().isoformat()
                },
                "message": f"命令已在后台启动，shell_id: {shell_id}",
                "next_actions": build_next_actions([
                    ("shell_session", "读取后台命令输出", "需要查看命令执行结果时", {"shell_id": shell_id, "action": "output"}),
                ])
            }
        
        # 不使用 text=True，手动处理编码
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            cwd=cwd,
            timeout=timeout_sec,
            env=env,
            executable=executable
        )
        
        # 手动解码，处理编码问题
        stdout_str = ""
        stderr_str = ""
        try:
            stdout_str = result.stdout.decode(use_encoding) if result.stdout else ""
        except (UnicodeDecodeError, AttributeError):
            try:
                stdout_str = result.stdout.decode("utf-8") if result.stdout else ""
            except (UnicodeDecodeError, AttributeError):
                stdout_str = result.stdout.decode("gbk") if result.stdout else ""
        
        try:
            stderr_str = result.stderr.decode(use_encoding) if result.stderr else ""
        except (UnicodeDecodeError, AttributeError):
            try:
                stderr_str = result.stderr.decode("utf-8") if result.stderr else ""
            except (UnicodeDecodeError, AttributeError):
                stderr_str = result.stderr.decode("gbk") if result.stderr else ""
        
        if result.returncode == 0:
            if stderr_str and stderr_str.strip():
                message = "命令执行成功（有警告输出）"
            else:
                message = "命令执行成功"
            _llm = format_output_for_llm(stdout_str, stderr_str)  # 小沈-2026-05-15
            return {
                "code": "SUCCESS",
                "data": {
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "returncode": result.returncode
                },
                "message": message,
                "llm_data": _llm,
                "next_actions": build_next_actions([
                    ("execute_shell_command", "继续执行后续命令", "需要执行更多命令时"),
                    ("find_command", "查找命令路径", "需要确认命令是否存在时"),
                ])
            }
        else:
            return {
                "code": "ERR_SHELL_EXEC",
                "data": {
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "returncode": result.returncode
                },
                "message": f"命令执行失败（退出码{result.returncode}）"
            }
    except subprocess.TimeoutExpired as e:
        return {
            "code": "ERR_SHELL_TIMEOUT",
            "data": {
                "stdout": "",
                "stderr": f"命令执行超时（{timeout}毫秒）",
                "returncode": -1
            },
            "message": f"命令执行超时（{timeout}毫秒）"
        }
    except Exception as e:
        return {
            "code": "ERR_SHELL_EXEC",
            "data": None,
            "message": f"命令执行失败: {str(e)}"
        }


def _get_working_directory() -> dict:
    """获取当前工作目录（内部辅助函数，不注册LLM）- 小健 2026-05-17 降级自 get_working_directory"""
    try:
        return {
            "code": "SUCCESS",
            "data": {
                "path": os.getcwd()
            },
            "message": "成功获取当前工作目录"
        }
    except Exception as e:
        return {
            "code": "ERR_SHELL_GET_CWD",
            "data": None,
            "message": f"获取工作目录失败: {str(e)}"
        }


def _check_path_exists(path: str) -> dict:
    """检查路径是否存在（内部辅助函数，不注册LLM）- 小健 2026-05-17 降级自 check_path_exists"""
    try:
        exists = os.path.exists(path)
        is_file = os.path.isfile(path) if exists else False
        is_dir = os.path.isdir(path) if exists else False
        return {
            "code": "SUCCESS",
            "data": {
                "exists": exists,
                "is_file": is_file,
                "is_directory": is_dir,
                "path": path
            },
            "message": "路径存在" if exists else "路径不存在"
        }
    except Exception as e:
        return {
            "code": "ERR_SHELL_CHECK_PATH",
            "data": None,
            "message": f"检查路径失败: {str(e)}"
        }

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
                return {
                    "code": "SUCCESS",
                    "data": {"available": True, "command": command, "path": cmd_path},
                    "message": f"命令 '{command}' 可用，路径: {cmd_path}",
                    "next_actions": build_next_actions([
                        ("execute_shell_command", "执行该命令", "确认命令可用后需要执行时", {"command": command}),
                    ])
                }
            else:
                return {
                    "code": "SUCCESS",
                    "data": {"available": False, "command": command, "path": None},
                    "message": f"命令 '{command}' 不可用"
                }
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
                return {
                    "code": "SUCCESS",
                    "data": {"command": command, "paths": paths, "count": len(paths)},
                    "message": f"找到 {len(paths)} 个路径",
                    "next_actions": build_next_actions([
                        ("execute_shell_command", "执行该命令", "确认命令可用后需要执行时", {"command": command}),
                    ])
                }
            else:
                return {
                    "code": "SUCCESS",
                    "data": {"command": command, "paths": [], "count": 0},
                    "message": f"命令 '{command}' 不可用"
                }
    except Exception as e:
        return {
            "code": "ERR_SHELL_FIND_COMMAND",
            "data": None,
            "message": f"查找命令失败: {str(e)}"
        }


def _read_stream_nonblocking(stream, encoding: str = "utf-8") -> str:
    """非阻塞读取子进程输出流 - 小沈 2026-05-05
    
    如果进程已结束，读取全部输出；
    如果进程仍在运行，读取当前可用的输出而不阻塞。
    """
    if stream is None:
        return ""
    
    import io
    try:
        if hasattr(stream, 'read1'):
            bytes_data = b""
            while True:
                chunk = stream.read1(4096)
                if not chunk:
                    break
                bytes_data += chunk
        else:
            bytes_data = stream.read()
    except (IOError, OSError):
        return ""
    
    if not bytes_data:
        return ""
    
    try:
        return bytes_data.decode(encoding)
    except UnicodeDecodeError:
        for fallback_enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
            try:
                return bytes_data.decode(fallback_enc)
            except UnicodeDecodeError:
                continue
        return bytes_data.decode("latin-1")

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
    encoding = None  # 小沈 2026-05-19: 已从Schema移除，实现自动回退
    tail = True  # 小沈 2026-05-19: 已从Schema移除，默认返回尾部最新输出
    cleanup = True  # 小沈 2026-05-19: 已从Schema移除，默认终止后清理
    if action == "output":
        shell_info = _background_shells.get(shell_id)
        if not shell_info:
            return {"code": "ERR_SHELL_NOT_FOUND", "data": None, "message": f"后台Shell会话不存在: {shell_id}"}
        process = shell_info.get("process")
        if not process:
            return {"code": "ERR_SHELL_NOT_FOUND", "data": None, "message": f"后台Shell会话无进程: {shell_id}"}
        use_encoding = encoding or "utf-8"
        stdout_str = _read_stream_nonblocking(process.stdout, use_encoding)
        stderr_str = _read_stream_nonblocking(process.stderr, use_encoding)
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
        if tail:
            stdout_lines = stdout_lines[-max_lines:]
        else:
            stdout_lines = stdout_lines[:max_lines]
        stdout_str = "\n".join(stdout_lines)
        return {
            "code": "SUCCESS",
            "data": {"shell_id": shell_id, "stdout": stdout_str, "stderr": stderr_str, "is_running": is_running},
            "message": "后台命令输出" if is_running else "后台命令已结束",
            "next_actions": build_next_actions([
                ("shell_session", "继续读取输出", "进程仍在运行需要持续监控时", {"shell_id": shell_id, "action": "output"}),
                ("shell_session", "终止后台命令", "需要停止后台进程或清理会话时", {"shell_id": shell_id, "action": "terminate"}),
            ])  # 小健 2026-05-19: 无论进程是否运行都提供terminate(清理会话防止内存泄漏)
        }
    elif action == "terminate":
        shell_info = _background_shells.get(shell_id)
        if not shell_info:
            return {"code": "ERR_SHELL_NOT_FOUND", "data": None, "message": f"后台Shell会话不存在: {shell_id}"}
        process = shell_info.get("process")
        if not process:
            if cleanup:
                _background_shells.pop(shell_id, None)
            return {"code": "SUCCESS", "data": {"shell_id": shell_id, "terminated": True, "force": force, "returncode": None}, "message": "会话已无进程", "next_actions": build_next_actions([
                ("execute_shell_command", "启动新的后台命令", "需要执行新的命令时"),
            ])}
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
        if cleanup:
            _background_shells.pop(shell_id, None)
        return {
            "code": "SUCCESS",
            "data": {"shell_id": shell_id, "terminated": terminated, "force": force, "returncode": returncode},
            "message": "已终止后台命令" if terminated else "终止失败",
            "next_actions": build_next_actions([
                ("execute_shell_command", "启动新的后台命令", "需要执行新的命令时"),
            ]) if terminated else build_next_actions([
                ("shell_session", "强制终止", "普通终止失败需要强制终止时", {"shell_id": shell_id, "action": "terminate", "force": True}),
            ])
        }
    else:
        return {
            "code": "ERR_INVALID_ACTION",
            "data": None,
            "message": f"无效的操作类型: {action}，必须是 output 或 terminate"
        }
