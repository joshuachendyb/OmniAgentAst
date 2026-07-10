"""Safety 模块 — 安全检查 + 文件操作安全

小欧 2026-07-10 拍平 file_safety/ 目录到 safety/
"""

from app.services.safety.operation_executor import FileSafetyConfig
from app.services.safety.hash_helper import compute_file_hash
from app.db.operation_queries import (
    row_to_operation_record, get_operation, get_session_operations,
    get_operation_task_id, query_file_operations, query_tree_operations,
    query_sankey_operations, query_animation_operations, query_mermaid_operations,
)
from app.services.safety.operation_recorder import (
    collect_file_info, update_op_failed, record_operation,
)
from app.services.safety.operation_executor import (
    backup_to_recycle_bin, execute_with_safety,
)
from app.services.safety.operation_rollback import (
    rollback_operation, rollback_session,
)
from app.services.safety.operation_cleanup import (
    cleanup_expired_backups,
)
from app.db.models.operation_models import OperationType, OperationStatus

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
