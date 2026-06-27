# validate/tools_file_path_checker.py — tool内部路径业务级检查（集中管理）
# 小沈 2026-06-27

from pathlib import Path
from typing import Optional, Tuple


def validate_path_for_write(file_path: str, content: str = "", append: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    写入操作的路径业务级检查（适用于write_text_file、edit_text_file及所有写入类工具）
    
    Returns: (is_valid, error_msg, warning_msg)
    """
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
    """
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
    """
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
