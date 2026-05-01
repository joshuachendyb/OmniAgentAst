# -*- coding: utf-8 -*-
"""
Shell 工具函数模块 - Shell命令执行工具

【创建时间】2026-04-29 小沈
【规范】按新规范使用 @register_tool 装饰器 + Pydantic 模型注册

包含：
- execute_command: 执行Shell命令
- get_working_directory: 获取当前工作目录
- change_directory: 切换工作目录
- check_path_exists: 检查路径是否存在
- get_shell_output: 获取后台shell输出
- terminate_shell: 终止后台shell

Author: 小沈 - 2026-04-29
"""

import os
import subprocess
import signal
import re
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from app.services.tools.registry import register_tool, ToolCategory

from app.services.tools.shell.shell_schema import (
    ExecuteCommandInput,
    GetWorkingDirectoryInput,
    ChangeDirectoryInput,
    CheckPathExistsInput,
    GetShellOutputInput,
    TerminateShellInput,
)


# 后台Shell会话管理器 - 小沈 2026-05-02
_background_shells: Dict[str, Dict[str, Any]] = {}


@register_tool(
    name="execute_command",
    description="""执行Shell命令并返回结果。

使用场景：
- 当用户需要执行系统命令时使用
- 当用户需要运行脚本或程序时使用
- 当用户需要获取系统信息（如ipconfig、dir等）时使用

参数说明：
- command: 要执行的Shell命令。必填参数
- cwd: 工作目录，如果为None则使用当前工作目录。可选参数
- timeout: 超时时间（秒），默认为30秒。可选参数

返回数据说明：
- stdout: 标准输出内容
- stderr: 标准错误内容
- returncode: 返回码（0表示成功）""",
    category=ToolCategory.SHELL,
    input_model=ExecuteCommandInput,
    examples=[
        {"command": "dir", "timeout": 10},
        {"command": "python --version", "timeout": 10},
        {"command": "dir /b D:/项目代码", "cwd": "D:/项目代码", "timeout": 30}
    ]
)
def execute_command(command: str, cwd: Optional[str] = None, timeout: int = 60) -> dict:
    """执行Shell命令 - 小沈 2026-05-01"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        # 【修复 2026-05-01 小沈】message更精确：区分returncode+stderr
        if result.returncode == 0:
            if result.stderr and result.stderr.strip():
                message = f"命令执行成功（有警告输出）"
            else:
                message = "命令执行成功"
        else:
            message = f"命令执行完成（退出码{result.returncode}）"
        return {
            "code": "SUCCESS",
            "data": {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            },
            "message": message
        }
    except subprocess.TimeoutExpired as e:
        # 【修复 2026-05-01 小沈】超时时也返回已捕获的输出
        return {
            "code": "ERR_SHELL_TIMEOUT",
            "data": {
                "stdout": e.stdout if e.stdout else "",
                "stderr": e.stderr if e.stderr else "",
                "returncode": -1
            },
            "message": f"命令执行超时（{timeout}秒）"
        }
    except Exception as e:
        return {
            "code": "ERR_SHELL_EXEC",
            "data": None,
            "message": f"命令执行失败: {str(e)}"
        }


@register_tool(
    name="get_working_directory",
    description="获取当前工作目录的完整路径。",
    category=ToolCategory.SHELL,
    input_model=GetWorkingDirectoryInput,
    examples=[{}]
)
def get_working_directory() -> dict:
    """获取当前工作目录"""
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


@register_tool(
    name="change_directory",
    description="改变当前工作目录到指定路径。",
    category=ToolCategory.SHELL,
    input_model=ChangeDirectoryInput,
    examples=[
        {"path": "D:/项目代码"},
        {"path": "C:/Users"}
    ]
)
def change_directory(path: str) -> dict:
    """切换工作目录"""
    try:
        os.chdir(path)
        return {
            "code": "SUCCESS",
            "data": {
                "success": True,
                "path": os.getcwd()
            },
            "message": f"已切换到目录: {os.getcwd()}"
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


@register_tool(
    name="check_path_exists",
    description="检查指定的文件或目录是否存在，并返回类型信息。",
    category=ToolCategory.SHELL,
    input_model=CheckPathExistsInput,
    examples=[
        {"path": "D:/项目代码"},
        {"path": "C:/Users/用户名/Documents/config.json"}
    ]
)
def check_path_exists(path: str) -> dict:
    """检查路径是否存在"""
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


@register_tool(
    name="get_shell_output",
    description="""获取后台运行的 shell 命令输出。

使用场景：
- 当用户需要获取后台命令的执行结果时使用
- 当用户想要检查后台命令是否完成时使用
- 当用户需要分批获取长命令输出时使用

参数说明：
- shell_id：后台 shell 的 ID，由 execute_shell_command 的 run_in_background=true 时返回
- filter：过滤输出的正则表达式（可选）
- encoding：输出编码（可选），默认utf-8
- max_lines：最大返回行数（可选），默认1000
- tail：是否只返回最后N行（可选），默认false

【重要】返回 shell 命令的 stdout 和 stderr 输出

使用示例：
- 获取输出：{"shell_id": "shell_abc123"}
- 过滤输出：{"shell_id": "shell_abc123", "filter": "ERROR"}""",
    category=ToolCategory.SHELL,
    input_model=GetShellOutputInput,
    examples=[
        {"shell_id": "shell_abc123"},
        {"shell_id": "shell_abc123", "filter": "ERROR|FAIL"},
        {"shell_id": "shell_abc123", "max_lines": 500, "tail": True}
    ]
)
def get_shell_output(
    shell_id: str,
    filter: Optional[str] = None,
    encoding: Optional[str] = None,
    max_lines: int = 1000,
    tail: bool = False
) -> dict:
    """获取后台shell命令输出 - 小沈 2026-05-02"""
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
        
        stdout_text = ""
        stderr_text = ""
        
        if process.stdout:
            stdout_bytes = process.stdout.read()
            try:
                stdout_text = stdout_bytes.decode(enc)
            except UnicodeDecodeError:
                for fallback_enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
                    try:
                        stdout_text = stdout_bytes.decode(fallback_enc)
                        break
                    except UnicodeDecodeError:
                        continue
        
        if process.stderr:
            stderr_bytes = process.stderr.read()
            try:
                stderr_text = stderr_bytes.decode(enc)
            except UnicodeDecodeError:
                for fallback_enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
                    try:
                        stderr_text = stderr_bytes.decode(fallback_enc)
                        break
                    except UnicodeDecodeError:
                        continue
        
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


@register_tool(
    name="terminate_shell",
    description="""终止运行中的后台 shell 会话。

使用场景：
- 当用户需要终止正在运行的后台命令时使用
- 当用户想要停止长时间运行的命令时使用
- 当用户需要清理后台进程时使用

参数说明：
- shell_id：要终止的 shell ID
- force：是否强制终止（可选），默认false
- cleanup：终止后是否清理临时文件（可选），默认true

【重要】强制终止后台进程，会丢失未读取的输出

使用示例：
- 终止后台shell：{"shell_id": "shell_abc123"}
- 强制终止：{"shell_id": "shell_abc123", "force": true}""",
    category=ToolCategory.SHELL,
    input_model=TerminateShellInput,
    examples=[
        {"shell_id": "shell_abc123"},
        {"shell_id": "shell_abc123", "force": True},
        {"shell_id": "shell_abc123", "force": True, "cleanup": True}
    ]
)
def terminate_shell(
    shell_id: str,
    force: bool = False,
    cleanup: bool = True
) -> dict:
    """终止后台shell会话 - 小沈 2026-05-02"""
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
