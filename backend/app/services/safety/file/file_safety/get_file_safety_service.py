# -*- coding: utf-8 -*-
"""
get_file_safety_service — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第556-565行
"""

from typing import Optional

from app.services.safety.file.file_safety.file_operation_safety import FileOperationSafety

_file_safety_instance: Optional[FileOperationSafety] = None


def get_file_safety_service() -> FileOperationSafety:
    """拷贝自 file_safety.py 第556-565行"""
    global _file_safety_instance
    if _file_safety_instance is None:
        _file_safety_instance = FileOperationSafety()
    return _file_safety_instance
