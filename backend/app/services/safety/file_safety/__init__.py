# -*- coding: utf-8 -*-
"""
file_safety — 文件操作安全模块 — 小健 2026-06-17 合并14文件为4文件

文件结构:
- config.py: 配置常量
- operation_queries.py: 所有只读查询
- operation_commands.py: 所有写入/备份/回滚命令
"""
from app.services.safety.file_safety.config import FileSafetyConfig
from app.services.tools.toolhelper.hash_helper import compute_file_hash
from app.services.safety.file_safety.operation_queries import (
    row_to_operation_record, get_operation, get_session_operations,
    get_operation_task_id, query_file_operations, query_tree_operations,
    query_sankey_operations, query_animation_operations, query_mermaid_operations,
)
from app.services.safety.file_safety.operation_commands import (
    backup_to_recycle_bin, record_operation, collect_file_info,
    update_op_failed, execute_with_safety, rollback_operation,
    rollback_session, cleanup_expired_backups,
)
from app.db.models.operation_enums import OperationType, OperationStatus

__all__ = [
    "FileSafetyConfig",
    "compute_file_hash", "row_to_operation_record", "backup_to_recycle_bin",
    "record_operation", "collect_file_info", "update_op_failed",
    "execute_with_safety", "rollback_operation", "get_operation_task_id",
    "rollback_session", "get_session_operations", "get_operation",
    "cleanup_expired_backups",
    "query_file_operations", "query_tree_operations", "query_sankey_operations",
    "query_animation_operations", "query_mermaid_operations",
    "OperationType", "OperationStatus",
]
