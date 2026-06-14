# -*- coding: utf-8 -*-
"""
build_list_where — 从 sessions.py 拷出

拷贝来源: sessions.py 第38-49行
"""

from typing import Optional, List, Tuple


def build_list_where(keyword: Optional[str], is_valid: Optional[bool],
                     for_count: bool = False) -> Tuple[str, List]:
    """拷贝自 sessions.py 第38-49行"""
    where = "WHERE is_deleted = FALSE"
    params: List = []
    if keyword:
        where += " AND title LIKE ?"
        params.append(f"%{keyword}%")
    if is_valid is not None:
        where += " AND is_valid = ?"
        params.append(1 if is_valid else 0)
    return where, params
