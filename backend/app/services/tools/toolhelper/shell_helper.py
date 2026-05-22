# -*- coding: utf-8 -*-
"""
Shell辅助函数模块 - Shell相关的内部辅助函数

【创建时间】2026-05-17 小沈
【说明】从 shell/shell_tools.py 迁移2个辅助函数
       这些函数作为内部Helper，不注册到tool_registry，供execute_shell_command等内部调用

包含函数（2个）：
- _check_shell_injection: 检查Shell注入风险（原shell_tools.py内部函数）
- _read_stream_nonblocking: 非阻塞读取子进程输出流（原shell_tools.py内部函数）

Author: 小沈 - 2026-05-17
"""

import io
import re
from typing import Optional


SHELL_INJECTION_PATTERNS = [
    (r'\$\(', '子shell执行 $()'),
    (r'`[^`]*`', '命令替换反引号'),
]


def _check_shell_injection(command: str) -> Optional[str]:
    """检查shell命令注入风险，返回错误描述或None - 小健 2026-05-13
    【2026-05-17 小沈】迁移到 toolhelper/shell_helper.py，供code_execution等复用
    """
    if not command or not command.strip():
        return None
    for pattern, desc in SHELL_INJECTION_PATTERNS:
        if re.search(pattern, command):
            return f"检测到高风险shell注入模式: {desc}"
    return None


def _read_stream_nonblocking(stream, encoding: str = "utf-8") -> str:
    """非阻塞读取子进程输出流 - 小沈 2026-05-05
    【2026-05-17 小沈】迁移到 toolhelper/shell_helper.py，供code_execution/system复用

    如果进程已结束，读取全部输出；
    如果进程仍在运行，读取当前可用的输出而不阻塞。
    """
    if stream is None:
        return ""
    
    try:
        if hasattr(stream, 'read1'):
            bytes_data = b""
            while True:
                chunk = stream.read1(4096)
                if not chunk:
                    break
                bytes_data += chunk
        else:
            bytes_data = stream.read()
    except (IOError, OSError):
        return ""
    
    if not bytes_data:
        return ""
    
    try:
        return bytes_data.decode(encoding)
    except UnicodeDecodeError:
        for fallback_enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
            try:
                return bytes_data.decode(fallback_enc)
            except UnicodeDecodeError:
                continue
        return bytes_data.decode("latin-1")


__all__ = [
    "_check_shell_injection",
    "_read_stream_nonblocking",
    "SHELL_INJECTION_PATTERNS",
]
