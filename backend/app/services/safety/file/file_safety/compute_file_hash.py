# -*- coding: utf-8 -*-
"""
compute_file_hash — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第72-78行
"""

from pathlib import Path


def compute_file_hash(file_path: Path) -> str:
    """拷贝自 file_safety.py 第72-78行"""
    try:
        from app.services.tools.toolhelper.hash_helper import compute_file_hash as _compute
        return _compute(str(file_path), algorithm="sha256")
    except Exception:
        return ""
