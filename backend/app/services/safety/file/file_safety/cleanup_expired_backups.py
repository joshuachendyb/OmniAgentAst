# -*- coding: utf-8 -*-
"""
cleanup_expired_backups — 从 file_safety.py 拷出

拷贝来源: file_safety.py 第516-553行
"""

import shutil
from datetime import datetime
from pathlib import Path

from app.db import db
from app.utils.logger import logger


def cleanup_expired_backups() -> int:
    """拷贝自 file_safety.py 第516-553行"""
    count = 0
    try:
        with db.get_conn("operations") as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT backup_path FROM file_operations 
                WHERE backup_expires_at < ? AND backup_path IS NOT NULL
            ''', (datetime.now(),))
            rows = cursor.fetchall()
            for (backup_path,) in rows:
                try:
                    path = Path(backup_path)
                    if path.exists():
                        if path.is_dir():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                        count += 1
                        logger.info(f"Cleaned up expired backup: {backup_path}")
                except Exception as e:
                    logger.error(f"Failed to cleanup backup {backup_path}: {e}")
        return count
    except Exception as e:
        logger.error(f"Failed to cleanup expired backups: {e}")
        return count
