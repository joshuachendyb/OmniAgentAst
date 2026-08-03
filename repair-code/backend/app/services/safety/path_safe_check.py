
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - #3 fix: 白名单盘符下增加系统保护目录拒绝(windows/program files/programdata等),
#    用 Path.parts[1] 精确只查盘符后第一级, 避免 C:\Users\MyProject\Program Files 误杀
# 2026-08-02 - 小欧 - 加固: _is_forbidden_path 新增磁盘根目录黑名单(C:\), 防止白名单盘符机制放行盘根删除
"""
path_safe_check — 文件路径越权校验（Safety层）

Safety层职责（本文件）：
  - 路径黑名单：禁止访问系统敏感路径（_is_forbidden_path）
  - 路径白名单：只允许在 ALLOWED_PATHS 内操作路径
  - 路径穿越(..)拒绝
  - 调用入口 validate_tool_path() 自动判断工具分类 + 找路径参数

工具层（validate/file_path_checker.py + validate/file_safety_checker.py）独立运行、互不调用：
  - 非空/保留字符/保留名/系统目录硬阻断/存在性+类型/业务警告
  - 内容安全检查 / 模块安装检查

从 file_tools.py 提取,供 safety 和 tools 共用,打破循环依赖

小沈 2026-06-17
小健 2026-06-23 增加系统敏感路径黑名单校验
小欧 2026-07-04 补充两层架构说明注释
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.tools.tool_constants import (
    FORBIDDEN_PATHS_EXACT,
    FORBIDDEN_PATHS_PREFIX,
    FORBIDDEN_PATHS_WINDOWS_EXACT,
    FORBIDDEN_PATHS_WINDOWS_PREFIX,
)
from app.logger import logger


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
        
        # 磁盘根目录(C:\)黑名单 — 白名单盘符机制允许盘根操作, 此处硬阻断 — 小欧 2026-08-02
        try:
            drive, rest = os.path.splitdrive(real_path_str)
            if drive and not rest.strip("\\/"):
                return True, f"禁止访问磁盘根目录: {file_path}"
        except Exception:
            pass
        
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
        # 【P1-21修复】异常时拒绝访问而非放行 — chendyg 2026-06-26
        return True, f"路径安全检查异常,拒绝访问: {file_path} ({e})"


def validate_path(file_path: str, allowed_paths: Optional[List[Path]] = None) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否在白名单内（Safety层）
    工具层的 validate_path() 先于本函数执行，已拦截空/保留字符/保留名/系统目录/不存在/类型不匹配
    本函数负责：黑名单/白名单/路径穿越拒绝

    Args:
        file_path: 待验证路径
        allowed_paths: 白名单(默认使用 ALLOWED_PATHS)

    Returns:
        (is_valid, error_message)

    小沈 2026-06-17 从 FileTools._validate_path 提取为纯函数
    小健 2026-06-23 增加黑名单优先检查
    小欧 2026-06-25 增加路径穿越(..)拒绝
    小欧 2026-06-26 拒绝空路径
    """
    if not file_path or not file_path.strip():
        return False, "路径为空"

    is_forbidden, forbidden_msg = _is_forbidden_path(file_path)
    if is_forbidden:
        return False, forbidden_msg

    # 路径穿越拒绝: 包含..的路径直接拒绝 — 小欧 2026-06-25
    try:
        # 检查原始路径的每个部分是否包含..
        path_parts = Path(file_path).parts
        if ".." in path_parts:
            return False, f"路径包含..,禁止路径穿越: {file_path}"
        # 也检查规范化解析后的路径（处理绝对路径中的..）
        resolved = os.path.realpath(file_path)
        original_resolved = os.path.realpath(os.path.dirname(file_path))
        if not resolved.startswith(original_resolved) and file_path != resolved:
            return False, f"路径穿越检测: {file_path} 解析为 {resolved}"
    except Exception as e:
        logger.warning(f"[path_safe_check] 路径校验异常: {file_path}: {e}")
        return False, f"路径校验异常: {file_path}"

    paths = allowed_paths or ALLOWED_PATHS
    try:
        real_path = Path(os.path.realpath(os.path.expanduser(file_path)))

        # 白名单盘符下仍拒绝系统保护目录（收紧范围）— 小欧 2026-07-18 #3 fix
        _SYSTEM_PROTECTED = frozenset({
            "windows", "program files", "program files (x86)",
            "programdata", "boot", "recovery",
        })
        _real_parts = real_path.parts
        if len(_real_parts) > 1 and _real_parts[1].lower() in _SYSTEM_PROTECTED:
            return False, f"路径位于系统保护目录,禁止操作: {file_path}"

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


# 路径相关的工具分类 — 5类工具涉及文件路径操作
_PATH_CATEGORIES = {
    ToolCategory.FILE, ToolCategory.DOCUMENT,
    ToolCategory.DATAANALYSIS, ToolCategory.NETWORK,
    ToolCategory.DESKTOP,
}

# 工具参数中可能的路径参数名
_PATH_PARAM_KEYS = ("path", "source_path", "target_path", "file_path",
                    "directory", "file_name", "destination_path", "output_path")


def validate_tool_path(tool_name: str, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    工具路径检查：自动判断分类 + 找路径参数 + 调validate_path
    
    将调度逻辑从 tool_safety_checker._check_known_risks 迁移至此，
    path相关的事情全部在 path_safe_check 中处理。
    小欧 2026-06-27
    """
    try:
        all_categories = tool_registry.get_categories()
        path_tools = set()
        for cat in _PATH_CATEGORIES:
            path_tools.update(all_categories.get(cat, []))

        if tool_name not in path_tools:
            return True, None

        real_path = None
        for key in _PATH_PARAM_KEYS:
            real_path = params.get(key)
            if real_path is not None:
                break

        if real_path is None:
            return True, None

        return validate_path(real_path)
    except Exception as e:
        return False, f"路径安全检查异常: {e}"


__all__ = ["ALLOWED_PATHS", "get_default_allowed_paths", "validate_path",
           "validate_tool_path", "_is_forbidden_path"]

