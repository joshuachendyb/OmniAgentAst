# -*- coding: utf-8 -*-
"""
collect_file_info — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第198-216行
"""

from pathlib import Path
from typing import Dict, Any

from app.services.safety.file.file_safety.compute_file_hash import compute_file_hash


def collect_file_info(path: Path) -> Dict[str, Any]:
    """拷贝自 file_safety.py 第198-216行"""
    if not path or not path.exists():
        return {"size": None, "hash": None, "extension": None, "is_directory": False}
    info = {
        "size": path.stat().st_size,
        "is_directory": path.is_dir(),
    }
    if path.is_file():
        info["hash"] = compute_file_hash(path)
        info["extension"] = path.suffix.lower() if path.suffix else None
    else:
        info["hash"] = None
        info["extension"] = None
    return info
