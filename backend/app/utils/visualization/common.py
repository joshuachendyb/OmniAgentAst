"""
可视化公共模块 - 数据类与共享查询/工具函数
包含 OperationNode, FlowData 数据类及 _query_file_operations, _count_op_stats, _format_size
小沈 2026-05-29 拆分自 file_visualization.py
"""
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

from app.db import db
from app.utils.logger import logger


@dataclass
class OperationNode:
    """操作节点（用于树形结构）"""
    id: str
    type: str
    name: str
    source: str = None
    destination: str = None
    status: str = "success"
    children: List['OperationNode'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class FlowData:
    """流程数据（用于Sankey图）"""
    source: str
    target: str
    value: int
    label: str


def query_file_operations(task_id: str) -> List[Tuple]:
    """查询 file_operations 表，返回所有操作记录（与 generate_html_report 共享）

    小沈 2026-05-25 重构拆分
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


def count_op_stats(operations: List[Tuple]) -> Dict[str, int]:
    """统计操作状态分布，返回 {total, success, failed, rolled_back}

    小沈 2026-05-25 重构拆分
    """
    return {
        "total": len(operations),
        "success": sum(1 for op in operations if op[3] == "success"),
        "failed": sum(1 for op in operations if op[3] == "failed"),
        "rolled_back": sum(1 for op in operations if "rollback" in str(op[3])),
    }


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"
