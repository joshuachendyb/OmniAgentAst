# -*- coding: utf-8 -*-
"""
operation_queries — 文件操作记录查询(数据层)

从 utils/visualization/common.py 下沉而来。
职责: 查询 file_operations 表,返回操作记录。
属于 service 层,visualization 层通过参数接收数据,不再直接访问 db。

小沈 2026-06-17
"""

from typing import List, Tuple, Dict, Any

from app.db import db
from app.utils.logger import logger


def query_file_operations(task_id: str) -> List[Tuple]:
    """查询 file_operations 表,返回所有操作记录

    小沈 2026-05-25 重构拆分
    小沈 2026-06-17 从 utils/visualization/common.py 下沉到 service 层
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status,
                   file_size, is_directory, created_at, error_message
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        operations = cursor.fetchall()
    return operations


def query_tree_operations(task_id: str) -> List[Tuple]:
    """查询树形操作记录

    小沈 2026-06-17 从 utils/visualization/tree_report.py 下沉
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_id, operation_type, source_path, destination_path, status
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        return cursor.fetchall()


def query_sankey_operations(task_id: str) -> List[Tuple]:
    """查询Sankey操作记录(仅成功的move/copy)

    小沈 2026-06-17 从 utils/visualization/sankey_report.py 下沉
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status
            FROM file_operations WHERE task_id = ? AND status = 'success'
            ORDER BY sequence_number ASC
        ''', (task_id,))
        return cursor.fetchall()


def query_animation_operations(task_id: str) -> List[Dict[str, Any]]:
    """查询动画操作记录,返回dict列表

    小沈 2026-06-17 从 utils/visualization/animation_report.py 下沉
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status, created_at
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        rows = cursor.fetchall()
    if not rows:
        return []
    return [
        {"type": op_type, "source": src, "destination": dst, "status": status, "timestamp": created_at}
        for op_type, src, dst, status, created_at in rows
    ]


def query_mermaid_operations(task_id: str) -> List[Tuple]:
    """查询Mermaid操作记录(含sequence_number)

    小沈 2026-06-17 从 utils/visualization/mermaid_report.py 下沉
    """
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT operation_type, source_path, destination_path, status, sequence_number
            FROM file_operations WHERE task_id = ?
            ORDER BY sequence_number ASC
        ''', (task_id,))
        return cursor.fetchall()


__all__ = ["query_file_operations", "query_tree_operations", "query_sankey_operations", "query_animation_operations", "query_mermaid_operations"]