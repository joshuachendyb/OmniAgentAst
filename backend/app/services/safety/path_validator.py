# -*- coding: utf-8 -*-
"""
path_validator — 文件路径越权校验

从 file_tools.py 提取,供 safety 和 tools 共用,打破循环依赖

小沈 2026-06-17
小健 2026-06-23 增加系统敏感路径黑名单校验
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple

from app.tools.tool_constants import (
    FORBIDDEN_PATHS_EXACT,
    FORBIDDEN_PATHS_PREFIX,
    FORBIDDEN_PATHS_WINDOWS_EXACT,
    FORBIDDEN_PATHS_WINDOWS_PREFIX,
)


def get_default_allowed_paths() -> List[Path]:
    """获取默认允许的路径列表 — 小沈 2026-06-17 从file_tools提取"""
    paths = [
        Path.home(),
        Path("/tmp"),
        Path("/var/tmp"),
    ]
    if os.name == 'nt':
        for letter in 'ABCDEFGHIJ':
            drive = Path(f"{letter}:/")
            if drive.exists():
                paths.append(drive)
    return paths


ALLOWED_PATHS: List[Path] = get_default_allowed_paths()


def _is_forbidden_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """检查路径是否在系统敏感路径黑名单中 — 小健 2026-06-23
    
    Args:
        file_path: 待检查路径
        
    Returns:
        (is_forbidden, error_message)
    """
    try:
        real_path = Path(os.path.realpath(os.path.expanduser(file_path)))
        real_path_str = str(real_path)
        real_path_lower = real_path_str.lower()
        
        if os.name == 'nt':
            for forbidden in FORBIDDEN_PATHS_WINDOWS_EXACT:
                if real_path_lower == forbidden.lower():
                    return True, f"禁止访问系统敏感文件: {file_path}"
            for forbidden_prefix in FORBIDDEN_PATHS_WINDOWS_PREFIX:
                if real_path_lower.startswith(forbidden_prefix.lower()):
                    return True, f"禁止访问系统敏感目录: {file_path}"
        
        for forbidden in FORBIDDEN_PATHS_EXACT:
            if real_path_str == forbidden:
                return True, f"禁止访问系统敏感文件: {file_path}"
        for forbidden_prefix in FORBIDDEN_PATHS_PREFIX:
            if real_path_str.startswith(forbidden_prefix):
                return True, f"禁止访问系统敏感目录: {file_path}"
        
        return False, None
    except Exception as e:
        return False, None


def validate_path(file_path: str, allowed_paths: Optional[List[Path]] = None) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否在白名单内

    Args:
        file_path: 待验证路径
        allowed_paths: 白名单(默认使用 ALLOWED_PATHS)

    Returns:
        (is_valid, error_message)

    小沈 2026-06-17 从 FileTools._validate_path 提取为纯函数
    小健 2026-06-23 增加黑名单优先检查
    """
    is_forbidden, forbidden_msg = _is_forbidden_path(file_path)
    if is_forbidden:
        return False, forbidden_msg
    
    paths = allowed_paths or ALLOWED_PATHS
    try:
        real_path = Path(os.path.realpath(os.path.expanduser(file_path)))

        for allowed in paths:
            allowed_real = Path(os.path.realpath(allowed))
            try:
                real_parts = Path(real_path).parts
                allowed_parts = Path(allowed_real).parts

                if len(real_parts) >= len(allowed_parts):
                    prefix_match = all(real_parts[i] == allowed_parts[i] for i in range(len(allowed_parts)))
                    if not prefix_match:
                        continue

                    if len(allowed_parts) == 1 and (allowed_parts[0].endswith(':') or allowed_parts[0].endswith(':\\') or allowed_parts[0].endswith(':/')):
                        if str(real_path) == str(allowed_real) or real_path.parts[0] == allowed_parts[0]:
                            return True, None
                    else:
                        if len(real_parts) >= len(allowed_parts):
                            return True, None
            except (ValueError, OSError):
                pass

        return False, f"路径 '{file_path}' 不在允许的操作范围内(仅允许:{', '.join(str(p) for p in paths[:5])}...)"

    except Exception as e:
        return False, f"路径验证失败: {str(e)}"


__all__ = ["ALLOWED_PATHS", "get_default_allowed_paths", "validate_path", "_is_forbidden_path"]