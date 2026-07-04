# validate/tools_file_path_checker.py — tool内部路径业务级检查（集中管理）
# 小沈 2026-06-27

from pathlib import Path
from typing import Optional, Tuple

_WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
                     'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4',
                     'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}


def _has_windows_reserved_name(file_path: str) -> Optional[str]:
    """检查路径是否包含Windows保留名 — 小欧 2026-07-04"""
    try:
        p = Path(file_path)
        for part in p.parts:
            name = part.split('.')[0].upper()
            if name in _WINDOWS_RESERVED:
                return part
    except Exception:
        pass
    return None


def validate_path_for_write(file_path: str, content: str = "", append: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    写入操作的路径业务级检查（适用于write_text_file、edit_text_file及所有写入类工具）
    
    Returns: (is_valid, error_msg, warning_msg)
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return False, "文件路径不能为空", None
    reserved = _has_windows_reserved_name(file_path)
    if reserved:
        return False, f"文件名包含Windows保留名: {reserved}", None
    path = Path(file_path)
    try:
        if path.exists() and path.is_file():
            if not append:
                old_size = path.stat().st_size
                if old_size > 1024 * 1024:
                    return True, None, f"覆盖大文件({old_size}字节)，请确认"
            else:
                old_size = path.stat().st_size
                if old_size > 100 * 1024 * 1024:
                    return True, None, f"追加到超大文件({old_size}字节)，请确认"
    except PermissionError:
        return False, f"无权限访问文件: {file_path}", None
    return True, None, None


def validate_path_for_delete(file_path: str, recursive: bool = False, force: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    删除操作的路径业务级检查（适用于delete_file）
    
    Returns: (is_valid, error_msg, warning_msg)
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return False, "文件路径不能为空", None
    reserved = _has_windows_reserved_name(file_path)
    if reserved:
        return False, f"文件名包含Windows保留名: {reserved}", None
    if recursive and Path(file_path).is_dir():
        return True, None, "递归删除目录，请确认"
    if force:
        return True, None, "永久删除（绕过回收站），请确认"
    return True, None, None


def validate_path_for_overwrite(source: str, destination: str, overwrite: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    覆盖操作的路径业务级检查（适用于move_file、copy_file）
    
    Returns: (is_valid, error_msg, warning_msg)
    注意：文件存在检查与实际操作之间存在时间窗口（TOCTOU），
    检查结果仅作为参考，不保证操作时的文件状态一致。
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(source, str) or not source.strip():
        return False, "源路径不能为空", None
    if not isinstance(destination, str) or not destination.strip():
        return False, "目标路径不能为空", None
    if overwrite and Path(destination).exists():
        return True, None, f"覆盖目标文件，请确认"
    return True, None, None


def validate_path_for_extract(output_dir: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    解压操作的路径业务级检查（适用于extract_archive）
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    if not output_dir:
        return True, None, None
    system_dirs = ["windows", "program files", "program files (x86)"]
    output_lower = output_dir.lower()
    for sd in system_dirs:
        if sd in output_lower:
            return True, None, f"解压到系统目录，请确认"
    return True, None, None


WINDOWS_SYSTEM_DIRS = [
    "/windows/", "/winnt/", "/program files/",
    "/program files (x86)/", "/system32/", "/system/",
]


def validate_not_system_path(file_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    检查路径是否涉及Windows系统关键目录

    Returns: (is_valid, error_msg, warning_msg)
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return False, "文件路径不能为空", None
    path_lower = file_path.lower().replace("\\", "/")
    path_after_drive = path_lower.split(":")[-1] if ":" in path_lower else path_lower
    for sd in WINDOWS_SYSTEM_DIRS:
        if path_after_drive.startswith(sd):
            return False, f"不允许操作系统目录下的文件: {file_path}", None
    return True, None, None
