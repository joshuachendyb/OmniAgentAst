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

【2026-05-06 小沈修正】深度测试发现的缺陷：
1. #1 working_dir空字符串校验漏洞 → is not None 判断
2. #2/#3 Windows中文编码问题 → 去掉text=True，手动UTF-8解码stdout/stderr，
   同时传PYTHONUTF8=1+PYTHONIOENCODING=utf-8环境变量
3. #6 TimeoutExpired的stdout/stderr可能是bytes → 安全解码函数

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
from app.services.tools.tool_result_utils import format_output_for_llm  # 小沈-2026-05-15

logger = logging.getLogger(__name__)


def _safe_decode(data, encodings=None):
    """安全解码bytes或返回str - 小沈 2026-05-06
    
    解决Windows下subprocess stdout/stderr编码问题：
    - 如果data是str，直接返回
    - 如果data是bytes，按encodings列表依次尝试解码
    - 如果data是None，返回空字符串
    - 统一将Windows的\\r\\n行尾转为\\n，保证跨平台一致性
    
    Args:
        data: bytes、str或None
        encodings: 尝试的编码列表，默认['utf-8', 'gbk', 'latin-1']
    
    Returns:
        str: 解码后的字符串
    """
    if data is None:
        return ""
    if isinstance(data, str):
        return data.replace('\r\n', '\n')
    if isinstance(data, bytes):
        for enc in (encodings or ['utf-8', 'gbk', 'latin-1']):
            try:
                return data.decode(enc).replace('\r\n', '\n')
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode('latin-1').replace('\r\n', '\n')
    return str(data)


def _get_utf8_env():
    """获取强制UTF-8的环境变量副本 - 小沈 2026-05-06
    
    设置PYTHONUTF8=1和PYTHONIOENCODING=utf-8，
    确保Python解释器用UTF-8模式读取源文件和输出。
    Node.js不受这些变量影响，但stdout解码走_safe_decode。
    """
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def execute_python(code: str, timeout: int = 30, working_dir: Optional[str] = None) -> dict:
    """执行Python代码 - 小沈 2026-05-02, 修正 2026-05-05(空字符串working_dir), 修正 2026-05-06(中文编码)"""
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
                cwd=working_dir,
                timeout=timeout,
                env=_get_utf8_env()
            )

            stdout_str = _safe_decode(result.stdout)
            stderr_str = _safe_decode(result.stderr)

            if result.returncode == 0:
                if stderr_str and stderr_str.strip():
                    message = "Python代码执行成功（有警告输出）"
                else:
                    message = "Python代码执行成功"
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
                message = f"Python代码执行失败（退出码{result.returncode}）"
                return {
                    "code": "ERR_EXEC_FAILED",
                    "data": {
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                        "returncode": result.returncode
                    },
                    "message": message
                }

        except subprocess.TimeoutExpired as e:
            return {
                "code": "ERR_EXEC_TIMEOUT",
                "data": {
                    "stdout": _safe_decode(e.stdout),
                    "stderr": _safe_decode(e.stderr),
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
    """执行JavaScript代码 - 小沈 2026-05-02, 修正 2026-05-05(空字符串working_dir), 修正 2026-05-06(中文编码)"""
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
                cwd=working_dir,
                timeout=timeout
            )

            stdout_str = _safe_decode(result.stdout)
            stderr_str = _safe_decode(result.stderr)

            if result.returncode == 0:
                if stderr_str and stderr_str.strip():
                    message = "JavaScript代码执行成功（有警告输出）"
                else:
                    message = "JavaScript代码执行成功"
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
                message = f"JavaScript代码执行失败（退出码{result.returncode}）"
                return {
                    "code": "ERR_EXEC_FAILED",
                    "data": {
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                        "returncode": result.returncode
                    },
                    "message": message
                }

        except subprocess.TimeoutExpired as e:
            return {
                "code": "ERR_EXEC_TIMEOUT",
                "data": {
                    "stdout": _safe_decode(e.stdout),
                    "stderr": _safe_decode(e.stderr),
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
