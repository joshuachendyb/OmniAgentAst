# -*- coding: utf-8 -*-
"""
通用工具公共Helper - 截断、路径安全、平台检查、Windows命令执行

【创建时间】2026-05-18 小沈
【说明】从各工具文件中提取的通用模式，供任意分类工具调用。
       不注册到tool_registry，不暴露给LLM。

【分层规范 - 小健 2026-05-27】
本文件属于【工具层helper】，使用 _response.py 的 build_success/build_error/build_warning
禁止使用 agent/tool_result_utils.py 的 create_xxx 函数

包含函数：
- safe_path_join: 安全路径拼接 + 防路径遍历
- check_windows_platform: 统一Windows平台检查
- run_windows_command: 统一Windows命令执行器（默认GBK编码）

Author: 小沈 - 2026-05-18
"""

import os
import platform
import subprocess
from app.constants import ERR_DESKTOP_NOT_WINDOWS
from typing import Any, Dict, Optional, Tuple
from app.services.tools._response import build_error, build_success


def _check_module(module_name: str) -> bool:
    """统一检查Python模块是否已安装 — 小沈 2026-05-18
    合并 document_tools._check_module + data_analysis_tools._check_pandas/_check_matplotlib/_check_openpyxl/_check_numpy
    委托给 exec_helper._check_module_available 获取版本信息
    """
    from app.services.tools.toolhelper.exec_helper import _check_module_available

    available, _ = _check_module_available(module_name)
    return available


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
        build_success/build_error 统一格式
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
        )
        stdout = result.stdout.decode(encoding, errors='ignore') if isinstance(result.stdout, bytes) else result.stdout
        stderr = result.stderr.decode(encoding, errors='ignore') if isinstance(result.stderr, bytes) else result.stderr
        if result.returncode == 0:
            return build_success(data={"returncode": result.returncode, "stdout": stdout, "stderr": stderr}, message="命令执行成功")
        else:
            return build_error(error_code="ERR_COMMAND_FAILED", message=f"命令返回非零退出码({result.returncode})", data={"returncode": result.returncode, "stdout": stdout, "stderr": stderr})
    except subprocess.TimeoutExpired:
        return build_error(error_code="ERR_COMMAND_TIMEOUT", message=f"命令执行超时({timeout}秒): {' '.join(cmd)}")
    except FileNotFoundError as e:
        return build_error(error_code="ERR_COMMAND_NOT_FOUND", message=f"命令未找到: {str(e)}")
    except Exception as e:
        return build_error(error_code="ERR_COMMAND_FAILED", message=f"命令执行失败: {str(e)}")


def check_windows_platform() -> bool:
    """检查当前平台是否为Windows"""
    import platform
    return platform.system().lower() == "windows"


__all__ = [
    "_check_module",
    "safe_path_join",
    "check_windows_platform",
    "run_windows_command",
]

