# -*- coding: utf-8 -*-
"""
Code Execution 工具函数模块 - 代码执行工具

【创建时间】2026-05-02 小沈
【2026-05-02 小沈重构】移除 @register_tool 装饰器，改为显式注册

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含：
- execute_python: 执行Python代码
- execute_javascript: 执行JavaScript代码

【2026-05-05 小沈修正】小健检查发现的问题：
1. 非零退出码返回SUCCESS的逻辑错误 → returncode!=0时返回ERR_EXEC_FAILED
2. Python缺少FileNotFoundError处理（JavaScript有而Python没有）
3. 裸except:pass吞掉异常 → 改为OSError + logger.warning
4. TimeoutExpired的stdout/stderr显式str转换保证类型安全

Author: 小沈 - 2026-05-02
"""

import os
import subprocess
import tempfile
import logging
from typing import Optional

from app.services.tools.code_execution.code_execution_schema import (
    ExecutePythonInput,
    ExecuteJavascriptInput,
)

logger = logging.getLogger(__name__)


def execute_python(code: str, timeout: int = 30, working_dir: Optional[str] = None) -> dict:
    """执行Python代码 - 小沈 2026-05-02, 小沈修正 2026-05-05, 小沈修正 2026-05-05(空字符串working_dir)"""
    if working_dir is not None and not os.path.isdir(working_dir):
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
                return {
                    "code": "SUCCESS",
                    "data": {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "returncode": result.returncode
                    },
                    "message": message
                }
            else:
                message = f"Python代码执行失败（退出码{result.returncode}）"
                return {
                    "code": "ERR_EXEC_FAILED",
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
                    "stdout": str(e.stdout or ""),
                    "stderr": str(e.stderr or ""),
                    "returncode": -1
                },
                "message": f"Python代码执行超时（{timeout}秒）"
            }
        finally:
            try:
                os.unlink(temp_file)
            except OSError as e:
                logger.warning(f"删除临时文件失败: {temp_file}, 错误: {e}")

    except FileNotFoundError:
        return {
            "code": "ERR_EXEC_PYTHON_NOT_FOUND",
            "data": None,
            "message": "未找到Python环境，请确认Python已安装且在PATH中"
        }
    except Exception as e:
        return {
            "code": "ERR_EXEC_PYTHON",
            "data": None,
            "message": f"Python代码执行失败: {str(e)}"
        }


def execute_javascript(code: str, timeout: int = 30, working_dir: Optional[str] = None) -> dict:
    """执行JavaScript代码 - 小沈 2026-05-02, 小沈修正 2026-05-05, 小沈修正 2026-05-05(空字符串working_dir)"""
    if working_dir is not None and not os.path.isdir(working_dir):
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
                return {
                    "code": "SUCCESS",
                    "data": {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "returncode": result.returncode
                    },
                    "message": message
                }
            else:
                message = f"JavaScript代码执行失败（退出码{result.returncode}）"
                return {
                    "code": "ERR_EXEC_FAILED",
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
                    "stdout": str(e.stdout or ""),
                    "stderr": str(e.stderr or ""),
                    "returncode": -1
                },
                "message": f"JavaScript代码执行超时（{timeout}秒）"
            }
        finally:
            try:
                os.unlink(temp_file)
            except OSError as e:
                logger.warning(f"删除临时文件失败: {temp_file}, 错误: {e}")

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
