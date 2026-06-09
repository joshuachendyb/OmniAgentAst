# -*- coding: utf-8 -*-
"""
FileSafetyConfig — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第23-39行
"""

from pathlib import Path


class FileSafetyConfig:
    """拷贝自 file_safety.py 第23-39行"""
    RECYCLE_BIN_PATH: Path = Path.home() / ".omniagent" / "recycle_bin"
    BACKUP_RETENTION_DAYS: int = 30
    PROJECT_ROOT = Path(__file__).resolve().parents[6]
    REPORT_PATH: Path = PROJECT_ROOT / "reports"

    @classmethod
    def ensure_directories(cls):
        cls.RECYCLE_BIN_PATH.mkdir(parents=True, exist_ok=True)
        cls.REPORT_PATH.mkdir(parents=True, exist_ok=True)
