# -*- coding: utf-8 -*-
"""
backup_to_recycle_bin — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第106-134行
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.utils.logger import logger
from app.services.safety.file.file_safety.config import FileSafetyConfig


def backup_to_recycle_bin(source_path: Path) -> Optional[Path]:
    """拷贝自 file_safety.py 第106-134行"""
    config = FileSafetyConfig()
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = config.RECYCLE_BIN_PATH / f"{timestamp}_{uuid4().hex[:8]}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / source_path.name
        if source_path.is_dir():
            shutil.copytree(source_path, backup_path)
        else:
            shutil.copy2(source_path, backup_path)
        logger.info(f"File backed up to recycle bin: {source_path} -> {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup file to recycle bin: {e}")
        return None
