# -*- coding: utf-8 -*-
"""
build_update_sql — 从 sessions.py 拷出

拷贝来源: sessions.py 第213-221行
"""

from typing import Tuple


def build_update_sql(mode: str) -> Tuple[str, str]:
    """拷贝自 sessions.py 第213-221行 — 小健 2026-06-18 DRY提取公共SET子句"""
    base_set = "title = ?, updated_at = ?"
    extra_set = "title_locked = ?, title_updated_at = ?, version = version + 1"
    set_clause = f"SET {base_set}, {extra_set}"
    where_clause = "AND is_deleted = FALSE"
    
    if mode == "optimistic":
        where_clause += " AND version = ?"
    
    return (set_clause, where_clause)
