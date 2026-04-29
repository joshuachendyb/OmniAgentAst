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

Author: 小沈 - 2026-04-29
"""

import os
import subprocess
from typing import Optional

from app.services.tools.registry import register_tool, ToolCategory

from app.services.tools.shell.shell_schema import (
    ExecuteCommandInput,
    GetWorkingDirectoryInput,
    ChangeDirectoryInput,
    CheckPathExistsInput,
)


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
def execute_command(command: str, cwd: Optional[str] = None, timeout: int = 30) -> dict:
    """执行Shell命令"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        return {
            "code": "SUCCESS",
            "data": {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            },
            "message": "命令执行成功" if result.returncode == 0 else "命令执行完成（有错误输出）"
        }
    except subprocess.TimeoutExpired:
        return {
            "code": "ERR_SHELL_TIMEOUT",
            "data": None,
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
