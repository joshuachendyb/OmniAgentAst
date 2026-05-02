# -*- coding: utf-8 -*-
"""
Code Execution 工具函数模块 - 代码执行工具

【创建时间】2026-05-02 小沈
【规范】按新规范使用 @register_tool 装饰器 + Pydantic 模型注册

包含：
- execute_python: 执行Python代码
- execute_javascript: 执行JavaScript代码

Author: 小沈 - 2026-05-02
"""

import os
import subprocess
import tempfile
from typing import Optional

from app.services.tools.registry import register_tool, ToolCategory

from app.services.tools.code_execution.code_execution_schema import (
    ExecutePythonInput,
    ExecuteJavascriptInput,
)


@register_tool(
    name="execute_python",
    description="""执行Python代码并返回结果。

使用场景：
- 当用户需要运行Python代码片段时使用
- 当用户需要快速验证Python代码逻辑时使用
- 当用户需要执行数据处理、计算等Python脚本时使用

参数说明：
- code: 要执行的Python代码。必填参数
- timeout: 超时时间（秒），默认为30秒。可选参数
- working_dir: 工作目录，如果为None则使用当前工作目录。可选参数

返回数据说明：
- stdout: 标准输出内容
- stderr: 标准错误内容
- returncode: 返回码（0表示成功）""",
    category=ToolCategory.SYSTEM,
    input_model=ExecutePythonInput,
    examples=[
        {"code": "print('Hello, World!')"},
        {"code": "import math\nprint(math.sqrt(16))"},
        {"code": "for i in range(5):\n    print(i)", "timeout": 10}
    ]
)
def execute_python(code: str, timeout: int = 30, working_dir: Optional[str] = None) -> dict:
    """执行Python代码 - 小沈 2026-05-02"""
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


@register_tool(
    name="execute_javascript",
    description="""执行JavaScript代码并返回结果。

使用场景：
- 当用户需要运行JavaScript代码片段时使用
- 当用户需要快速验证JavaScript代码逻辑时使用
- 当用户需要执行Node.js脚本时使用

参数说明：
- code: 要执行的JavaScript代码。必填参数
- timeout: 超时时间（秒），默认为30秒。可选参数
- working_dir: 工作目录，如果为None则使用当前工作目录。可选参数

返回数据说明：
- stdout: 标准输出内容
- stderr: 标准错误内容
- returncode: 返回码（0表示成功）

注意：需要系统已安装Node.js环境""",
    category=ToolCategory.SYSTEM,
    input_model=ExecuteJavascriptInput,
    examples=[
        {"code": "console.log('Hello, World!');"},
        {"code": "const result = Math.sqrt(16);\nconsole.log(result);"},
        {"code": "for(let i=0; i<5; i++) {\n  console.log(i);\n}", "timeout": 10}
    ]
)
def execute_javascript(code: str, timeout: int = 30, working_dir: Optional[str] = None) -> dict:
    """执行JavaScript代码 - 小沈 2026-05-02"""
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
