# -*- coding: utf-8 -*-
"""
file_safety — 文件操作安全模块 — 小健 2026-06-17 合并14文件为4文件

文件结构:
- config.py: 配置常量
- operation_queries.py: 所有只读查询
- operation_recorder.py: 操作记录和文件信息收集
- operation_executor.py: 操作执行和备份
- operation_rollback.py: 操作回滚
- operation_cleanup.py: 操作清理

小欧 2026-06-18 拆分operation_commands.py为4个模块，遵守SRP
"""
from app.services.safety.file_safety.config import FileSafetyConfig
from app.services.safety.hash_helper import compute_file_hash
from app.db.operation_queries import (
    row_to_operation_record, get_operation, get_session_operations,
    get_operation_task_id, query_file_operations, query_tree_operations,
    query_sankey_operations, query_animation_operations, query_mermaid_operations,
)
from app.services.safety.file_safety.operation_recorder import (
    collect_file_info, update_op_failed, record_operation,
)
from app.services.safety.file_safety.operation_executor import (
    backup_to_recycle_bin, execute_with_safety,
)
from app.services.safety.file_safety.operation_rollback import (
    rollback_operation, rollback_session,
)
from app.services.safety.file_safety.operation_cleanup import (
    cleanup_expired_backups,
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
