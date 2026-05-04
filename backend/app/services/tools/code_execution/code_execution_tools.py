# -*- coding: utf-8 -*-
"""
Code Execution 工具函数模块 - 代码执行工具

【创建时间】2026-05-02 小沈
【2026-05-02 小沈重构】移除 @register_tool 装饰器，改为显式注册

包含：
- execute_python: 执行Python代码
- execute_javascript: 执行JavaScript代码

Author: 小沈 - 2026-05-02
"""

import os
import subprocess
import tempfile
from typing import Optional

from app.services.tools.code_execution.code_execution_schema import (
    ExecutePythonInput,
    ExecuteJavascriptInput,
)


def execute_python(code: str, timeout: int = 30, working_dir: Optional[str] = None) -> dict:
    """执行Python代码 - 小沈 2026-05-02"""
    # 验证working_dir是否存在
    if working_dir and not os.path.isdir(working_dir):
        return {
            "code": "ERR_EXEC_INVALID_DIR",
            "data": None,
            "message": f"工作目录不存在: {working_dir}"
        }
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=timeout
            )
            
            if result.returncode == 0:
                if result.stderr and result.stderr.strip():
                    message = "Python代码执行成功（有警告输出）"
                else:
                    message = "Python代码执行成功"
            else:
                message = f"Python代码执行完成（退出码{result.returncode}）"
            
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
            return {
                "code": "ERR_EXEC_TIMEOUT",
                "data": {
                    "stdout": e.stdout if e.stdout else "",
                    "stderr": e.stderr if e.stderr else "",
                    "returncode": -1
                },
                "message": f"Python代码执行超时（{timeout}秒）"
            }
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
                
    except Exception as e:
        return {
            "code": "ERR_EXEC_PYTHON",
            "data": None,
            "message": f"Python代码执行失败: {str(e)}"
        }


def execute_javascript(code: str, timeout: int = 30, working_dir: Optional[str] = None) -> dict:
    """执行JavaScript代码 - 小沈 2026-05-02"""
    # 验证working_dir是否存在
    if working_dir and not os.path.isdir(working_dir):
        return {
            "code": "ERR_EXEC_INVALID_DIR",
            "data": None,
            "message": f"工作目录不存在: {working_dir}"
        }
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ['node', temp_file],
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=timeout
            )
            
            if result.returncode == 0:
                if result.stderr and result.stderr.strip():
                    message = "JavaScript代码执行成功（有警告输出）"
                else:
                    message = "JavaScript代码执行成功"
            else:
                message = f"JavaScript代码执行完成（退出码{result.returncode}）"
            
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
            return {
                "code": "ERR_EXEC_TIMEOUT",
                "data": {
                    "stdout": e.stdout if e.stdout else "",
                    "stderr": e.stderr if e.stderr else "",
                    "returncode": -1
                },
                "message": f"JavaScript代码执行超时（{timeout}秒）"
            }
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
                
    except FileNotFoundError:
        return {
            "code": "ERR_EXEC_NODE_NOT_FOUND",
            "data": None,
            "message": "未找到Node.js环境，请先安装Node.js"
        }
    except Exception as e:
        return {
            "code": "ERR_EXEC_JAVASCRIPT",
            "data": None,
            "message": f"JavaScript代码执行失败: {str(e)}"
        }
