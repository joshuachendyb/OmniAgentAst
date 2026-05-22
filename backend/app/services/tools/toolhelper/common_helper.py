# -*- coding: utf-8 -*-
"""
通用工具公共Helper - 截断、路径安全、平台检查、Windows命令执行

【创建时间】2026-05-18 小沈
【说明】从各工具文件中提取的通用模式，供任意分类工具调用。
       不注册到tool_registry，不暴露给LLM。

包含函数：
- truncate_value: 统一截断入口（整合truncate_text + make_json_safe）
- safe_path_join: 安全路径拼接 + 防路径遍历
- check_windows_platform: 统一Windows平台检查
- run_windows_command: 统一Windows命令执行器（默认GBK编码）

Author: 小沈 - 2026-05-18
"""

import importlib
import os
import platform
import subprocess
from typing import Any, Dict, Optional, Tuple


def _check_module(module_name: str) -> bool:
    """统一检查Python模块是否已安装 — 小沈 2026-05-18
    合并 document_tools._check_module + data_analysis_tools._check_pandas/_check_matplotlib/_check_openpyxl/_check_numpy
    """
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def truncate_value(
    value: Any,
    max_chars: int = 5000,
    max_depth: int = 5,
) -> Tuple[Any, bool]:
    """统一截断入口 - 小沈 2026-05-18

    整合 truncate_text + make_json_safe 逻辑，
    支持字符串截断和字典/列表深度截断。

    Args:
        value: 要截断的值
        max_chars: 字符串最大长度
        max_depth: 字典/列表最大深度

    Returns:
        (截断后的值, 是否截断)
    """
    truncated = False

    if isinstance(value, str):
        if len(value) > max_chars:
            return value[:max_chars] + f"...[截断，原长度{len(value)}]", True
        return value, False

    if isinstance(value, dict):
        if max_depth <= 0:
            return f"...[深度截断，字典{len(value)}项]", True
        result = {}
        for k, v in value.items():
            result[k], t = truncate_value(v, max_chars, max_depth - 1)
            if t:
                truncated = True
        return result, truncated

    if isinstance(value, (list, tuple)):
        if max_depth <= 0:
            return f"...[深度截断，{type(value).__name__}{len(value)}项]", True
        result = []
        for item in value:
            r, t = truncate_value(item, max_chars, max_depth - 1)
            result.append(r)
            if t:
                truncated = True
        return result, truncated

    return value, False


def safe_path_join(base_dir: str, *paths: str) -> Optional[str]:
    """安全路径拼接 + 防路径遍历 - 小沈 2026-05-18

    Args:
        base_dir: 基础目录
        *paths: 要拼接的路径片段

    Returns:
        拼接后的绝对路径，如果检测到路径遍历则返回None
    """
    try:
        result = os.path.normpath(os.path.join(base_dir, *paths))
        base = os.path.normpath(base_dir)
        if not result.startswith(base + os.sep) and result != base:
            return None
        return result
    except Exception:
        return None


def check_windows_platform() -> Optional[Dict[str, Any]]:
    """统一Windows平台检查 - 小沈 2026-05-18

    替代 desktop_tools + system_tools 中6处 platform.system() 判断。

    Returns:
        None: 平台为Windows
        Dict: 错误信息（非Windows平台）
    """
    if platform.system() != "Windows":
        return {
            "code": "ERR_DESKTOP_NOT_WINDOWS",
            "data": None,
            "message": "此功能仅支持 Windows 系统"
        }
    return None


def run_windows_command(
    cmd: list,
    timeout: int = 30,
    encoding: str = "gbk",
) -> Dict[str, Any]:
    """统一Windows命令执行器 - 小沈 2026-05-18

    默认GBK编码，替代 system_tools 中4处 subprocess.run(... encoding='gbk') 模式。

    Args:
        cmd: 命令列表，如 ["schtasks", "/query", "/fo", "LIST"]
        timeout: 超时秒数
        encoding: 输出编码，默认gbk（Windows中文环境）

    Returns:
        {"returncode": int, "stdout": str, "stderr": str}
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
        )
        stdout = result.stdout.decode(encoding, errors='ignore') if isinstance(result.stdout, bytes) else result.stdout
        stderr = result.stderr.decode(encoding, errors='ignore') if isinstance(result.stderr, bytes) else result.stderr
        return {
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"命令执行超时({timeout}秒): {' '.join(cmd)}",
        }
    except FileNotFoundError as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"命令未找到: {str(e)}",
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"命令执行失败: {str(e)}",
        }


__all__ = [
    "_check_module",
    "truncate_value",
    "safe_path_join",
    "check_windows_platform",
    "run_windows_command",
]
