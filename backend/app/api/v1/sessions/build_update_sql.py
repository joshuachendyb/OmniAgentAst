# -*- coding: utf-8 -*-
"""
build_update_sql — 从 sessions.py 拷出

拷贝来源: sessions.py 第213-221行
"""

from typing import Tuple


def build_update_sql(mode: str) -> Tuple[str, str]:
    """拷贝自 sessions.py 第213-221行"""
    base_set = "title = ?, updated_at = ?"
    if mode == "optimistic":
        return (
            f"SET {base_set}, title_locked = ?, title_updated_at = ?, version = version + 1",
            "AND is_deleted = FALSE AND version = ?",
        )
    return f"SET {base_set}, title_locked = ?, title_updated_at = ?, version = version + 1", "AND is_deleted = FALSE"
