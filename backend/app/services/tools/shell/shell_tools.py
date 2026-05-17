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
- get_shell_output: 获取后台shell输出
- terminate_shell: 终止后台shell

内部辅助函数（不注册LLM）：
- _get_working_directory: 获取当前工作目录（已降级，execute_shell_command内部使用）
- _check_path_exists: 检查路径是否存在（已降级，内部工具可用）

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

from app.services.tools.tool_result_utils import format_output_for_llm  # 小沈-2026-05-15


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
    timeout: int = 30000,  # 【修复 2026-05-14 小沈】300s→30s，curl等网络命令5分钟超时导致服务卡死
    run_in_background: bool = False,
    cwd: Optional[str] = None,
    encoding: Optional[str] = None,
    env_vars: Optional[dict] = None,
    run_as_admin: bool = False
) -> dict:
    """执行Shell命令 - 小沈 2026-05-04 正确实现encoding参数"""
    timeout_sec = timeout / 1000.0
    
    env = None
    if env_vars:
        env = os.environ.copy()
        env.update(env_vars)
    
    if shell_type == "cmd":
        executable = None  # shell=True时使用COMSPEC默认cmd.exe - 小沈 2026-05-06
    else:
        executable = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
    
    # run_as_admin: 标记但 subprocess 不支持提权，实际执行受限于当前进程权限
    # 如果需要提权，需要使用 ctypes.win32api 或其他方式
    if run_as_admin:
        if env is None:
            env = os.environ.copy()
        env["_RUN_AS_ADMIN"] = "1"
    
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
                "message": f"命令已在后台启动，shell_id: {shell_id}"
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
                "llm_data": _llm
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


def check_command_available(command: str) -> dict:
    """检查命令是否可用 - 小沈 2026-05-04
    【2026-05-17 小沈 已弃用】请使用 find_command(command) 代替
    """
    return find_command(command, all_paths=False)


def locate_command(command: str) -> dict:
    """查找命令的所有可能路径 - 小沈 2026-05-04
    【2026-05-17 小沈 已弃用】请使用 find_command(command, all_paths=True) 代替
    """
    return find_command(command, all_paths=True)


def get_working_directory() -> dict:
    """获取当前工作目录 - 小沈 2026-05-04"""
    try:
        return {
            "code": "SUCCESS",
            "data": {"path": os.getcwd()},
            "message": "成功获取当前工作目录"
        }
    except Exception as e:
        return {
            "code": "ERR_SHELL_GET_CWD",
            "data": None,
            "message": f"获取工作目录失败: {str(e)}"
        }


def change_directory(path: str) -> dict:
    """切换工作目录 - 小沈 2026-05-04"""
    try:
        os.chdir(path)
        return {
            "code": "SUCCESS",
            "data": {"success": True, "path": os.getcwd()},
            "message": f"已切换目录: {os.getcwd()}"
        }
    except FileNotFoundError:
        return {
            "code": "ERR_SHELL_PATH_NOT_FOUND",
            "data": None,
            "message": f"目录不存在: {path}"
        }
    except PermissionError:
        return {
            "code": "ERR_SHELL_PERMISSION",
            "data": None,
            "message": f"没有权限访问: {path}"
        }
    except Exception as e:
        return {
            "code": "ERR_SHELL_CHANGE_DIR",
            "data": None,
            "message": f"切换目录失败: {str(e)}"
        }


def check_path_exists(path: str) -> dict:
    """检查路径是否存在 - 小沈 2026-05-04"""
    try:
        exists = os.path.exists(path)
        is_file = os.path.isfile(path) if exists else False
        is_dir = os.path.isdir(path) if exists else False
        return {
            "code": "SUCCESS",
            "data": {"exists": exists, "is_file": is_file, "is_directory": is_dir, "path": path},
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
                    "message": f"命令 '{command}' 可用，路径: {cmd_path}"
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
                    "message": f"找到 {len(paths)} 个路径"
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


def get_shell_output(
    shell_id: str,
    filter: Optional[str] = None,
    encoding: Optional[str] = None,
    max_lines: int = 1000,
    tail: bool = False
) -> dict:
    """获取后台shell命令输出 - 小沈 2026-05-02
    【2026-05-17 小沈 已弃用LLM暴露】请使用 shell_session(action="output") 代替
    """
    try:
        if shell_id not in _background_shells:
            return {
                "code": "ERR_SHELL_NOT_FOUND",
                "data": None,
                "message": f"后台shell不存在: {shell_id}"
            }
        
        shell_info = _background_shells[shell_id]
        process = shell_info.get("process")
        
        if process is None:
            return {
                "code": "ERR_SHELL_NO_PROCESS",
                "data": None,
                "message": f"shell进程不存在: {shell_id}"
            }
        
        enc = encoding or "utf-8"
        
        stdout_text = _read_stream_nonblocking(process.stdout, enc)
        stderr_text = _read_stream_nonblocking(process.stderr, enc)
        
        stdout_lines = stdout_text.splitlines() if stdout_text else []
        stderr_lines = stderr_text.splitlines() if stderr_text else []
        
        if filter:
            try:
                pattern = re.compile(filter, re.IGNORECASE)
                stdout_lines = [line for line in stdout_lines if pattern.search(line)]
                stderr_lines = [line for line in stderr_lines if pattern.search(line)]
            except re.error as e:
                return {
                    "code": "ERR_SHELL_FILTER_INVALID",
                    "data": None,
                    "message": f"无效的正则表达式: {filter}, 错误: {str(e)}"
                }
        
        if tail:
            stdout_lines = stdout_lines[-max_lines:]
            stderr_lines = stderr_lines[-max_lines:]
        else:
            if len(stdout_lines) > max_lines:
                stdout_lines = stdout_lines[:max_lines]
            if len(stderr_lines) > max_lines:
                stderr_lines = stderr_lines[:max_lines]
        
        truncated = len(stdout_text.splitlines()) > max_lines or len(stderr_text.splitlines()) > max_lines
        
        return {
            "code": "SUCCESS",
            "data": {
                "shell_id": shell_id,
                "stdout": "\n".join(stdout_lines),
                "stderr": "\n".join(stderr_lines),
                "stdout_lines": len(stdout_lines),
                "stderr_lines": len(stderr_lines),
                "truncated": truncated,
                "is_running": process.poll() is None
            },
            "message": "成功获取shell输出" + ("（输出已截断）" if truncated else "")
        }
    
    except Exception as e:
        return {
            "code": "ERR_SHELL_GET_OUTPUT",
            "data": None,
            "message": f"获取shell输出失败: {str(e)}"
        }


def terminate_shell(
    shell_id: str,
    force: bool = False,
    cleanup: bool = True
) -> dict:
    """终止后台shell会话 - 小沈 2026-05-02
    【2026-05-17 小沈 已弃用LLM暴露】请使用 shell_session(action="terminate") 代替
    """
    try:
        if shell_id not in _background_shells:
            return {
                "code": "ERR_SHELL_NOT_FOUND",
                "data": None,
                "message": f"后台shell不存在: {shell_id}"
            }
        
        shell_info = _background_shells[shell_id]
        process = shell_info.get("process")
        
        if process is None:
            del _background_shells[shell_id]
            return {
                "code": "SUCCESS",
                "data": {"shell_id": shell_id, "terminated": True},
                "message": f"shell会话已清理: {shell_id}"
            }
        
        if process.poll() is not None:
            del _background_shells[shell_id]
            return {
                "code": "SUCCESS",
                "data": {
                    "shell_id": shell_id,
                    "terminated": True,
                    "already_stopped": True,
                    "returncode": process.returncode
                },
                "message": f"shell进程已停止: {shell_id}"
            }
        
        try:
            if force:
                process.kill()
            else:
                process.terminate()
            
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if not force:
                    process.kill()
                    process.wait(timeout=5)
        
        except ProcessLookupError:
            pass
        except Exception as e:
            return {
                "code": "ERR_SHELL_TERMINATE",
                "data": None,
                "message": f"终止进程失败: {str(e)}"
            }
        
        returncode = process.returncode
        
        del _background_shells[shell_id]
        
        return {
            "code": "SUCCESS",
            "data": {
                "shell_id": shell_id,
                "terminated": True,
                "force": force,
                "returncode": returncode,
                "cleanup": cleanup
            },
            "message": f"成功终止shell会话: {shell_id}" + ("（强制终止）" if force else "")
        }
    
    except Exception as e:
        return {
            "code": "ERR_SHELL_TERMINATE",
            "data": None,
            "message": f"终止shell失败: {str(e)}"
        }


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
    encoding: Optional[str] = None,
    max_lines: int = 1000,
    tail: bool = False,
    force: bool = False,
    cleanup: bool = True,
) -> dict:
    """后台Shell会话管理 - 小沈 2026-05-17
    合并 get_shell_output + terminate_shell

    Args:
        shell_id: 后台Shell会话ID
        action: 操作类型。output=读取输出, terminate=终止会话
        filter: 输出过滤正则（action="output"时生效）
        encoding: 输出编码（action="output"时生效）
        max_lines: 最大返回行数（action="output"时生效）
        tail: 只返回最后N行（action="output"时生效）
        force: 强制终止（action="terminate"时生效）
        cleanup: 终止后清理资源（action="terminate"时生效）

    Returns:
        {code, data, message}
    """
    if action == "output":
        return get_shell_output(shell_id, filter=filter, encoding=encoding,
                                max_lines=max_lines, tail=tail)
    elif action == "terminate":
        return terminate_shell(shell_id, force=force, cleanup=cleanup)
    else:
        return {
            "code": "ERR_INVALID_ACTION",
            "data": None,
            "message": f"无效的操作类型: {action}，必须是 output 或 terminate"
        }
