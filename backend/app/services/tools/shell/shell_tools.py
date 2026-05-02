# -*- coding: utf-8 -*-
"""
Shell 工具函数模块 - Shell命令执行工具

【创建时间】2026-04-29 小沈
【规范】2026-05-02 小沈 移除 @register_tool 装饰器，改由 shell_register.py 显式注册

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


# 后台Shell会话管理器 - 小沈 2026-05-02
_background_shells: Dict[str, Dict[str, Any]] = {}


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
