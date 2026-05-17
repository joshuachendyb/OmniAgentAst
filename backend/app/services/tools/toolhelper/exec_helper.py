# -*- coding: utf-8 -*-
"""
代码执行辅助函数模块 - 代码执行相关的内部辅助函数

【创建时间】2026-05-17 小沈
【说明】从 environment/env_check_tools.py 迁移4个检查型函数
       这些函数作为内部Helper，不注册到tool_registry，仅供execute_python/execute_javascript内部调用

包含函数（4个）：
- _check_python_available: 检查Python环境可用性（内部Helper）
- _validate_code_safety: 验证代码安全性（内部Helper）
- _check_node_available: 检查Node.js环境可用性（内部Helper）
- _check_module_available: 检查Python模块可用性（内部Helper）

Author: 小沈 - 2026-05-17
"""

import importlib
import re
import subprocess
import sys
from typing import List, Tuple


DANGEROUS_PATTERNS = [
    (r"os\.system\s*\(", "系统调用(os.system)"),
    (r"subprocess\.(call|run|Popen|check_output)\s*\(", "子进程调用(subprocess)"),
    (r"shutil\.rmtree\s*\(", "递归删除目录(shutil.rmtree)"),
    (r"os\.remove\s*\(", "删除文件(os.remove)"),
    (r"os\.unlink\s*\(", "删除文件(os.unlink)"),
    (r"__import__\s*\(", "动态导入(__import__)"),
    (r"eval\s*\(", "动态执行(eval)"),
    (r"exec\s*\(", "动态执行(exec)"),
    (r"compile\s*\(", "动态编译(compile)"),
    (r"open\s*\(.*[\'\"]w[\'\"]", "写入文件操作"),
    (r"socket\s*\.", "网络Socket操作"),
    (r"requests\.(get|post|put|delete|patch)\s*\(", "HTTP请求(requests)"),
    (r"urllib\.request", "URL请求(urllib)"),
]


def _check_python_available() -> bool:
    """检查Python是否可用（Helper，不暴露给LLM） - 小沈 2026-05-17

    execute_python 已通过 try/except FileNotFoundError 覆盖此场景，
    此函数供内部预检使用。

    Returns:
        bool: Python环境是否可用
    """
    try:
        return sys.executable is not None
    except Exception:
        return False


def _validate_code_safety(code: str) -> List[str]:
    """验证代码安全性（Helper，不暴露给LLM） - 小沈 2026-05-17

    检查代码是否包含危险模式，返回风险描述列表。
    execute_python(safety_check=True) 会自动调用此函数。

    Args:
        code: 要验证的代码字符串

    Returns:
        List[str]: 安全风险描述列表，空列表表示安全
    """
    warnings = []
    for pattern, desc in DANGEROUS_PATTERNS:
        if re.search(pattern, code):
            warnings.append(desc)
    return warnings


def _check_node_available() -> bool:
    """检查Node.js是否可用（Helper，不暴露给LLM） - 小沈 2026-05-17

    execute_javascript 已内置 FileNotFoundError 捕获，
    此函数供内部预检使用。

    Returns:
        bool: Node.js环境是否可用
    """
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_module_available(module_name: str) -> Tuple[bool, str]:
    """检查Python模块是否可用（Helper，不暴露给LLM） - 小沈 2026-05-17

    等价于 execute_python("import pandas; print(pandas.__version__)")，
    此函数供内部预检使用，返回(是否可用, 版本号)。

    Args:
        module_name: 模块名称，如 "pandas"、"numpy"

    Returns:
        Tuple[bool, str]: (是否可用, 版本号)
    """
    try:
        mod = importlib.import_module(module_name)
        return True, getattr(mod, "__version__", "unknown")
    except ImportError:
        return False, ""


__all__ = [
    "_check_python_available",
    "_validate_code_safety",
    "_check_node_available",
    "_check_module_available",
]
