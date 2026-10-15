# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - 拍平 file_safety/ 目录到 safety/
# 2026-07-26 - 小沈 - import 路径对应 operation_record/operation_backup 改名+职责理顺
# 2026-08-12 - 小欧 - A2-内部环(方案4.2.3): FileSafetyConfig 导入改 models, cleanup_expired_backups 导入改 operation_maintenance
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件全部 import 由 app.services.safety.xxx 改 app.safety.xxx(配合 tools 禁 app.services 守护规则)
"""Safety 模块 — 安全检查 + 文件操作安全

小欧 2026-07-10 拍平 file_safety/ 目录到 safety/
"""

from app.safety.file_safety_config import FileSafetyConfig
from app.safety.operation_record import (
    collect_file_info, update_op_failed, record_operation,
    execute_with_safety,
)
from app.safety.file_hasher import compute_file_hash
from app.db.operation_queries import (
    row_to_operation_record, get_operation, get_session_operations,
    get_operation_task_id, query_file_operations, query_tree_operations,
    query_sankey_operations, query_animation_operations, query_mermaid_operations,
)
from app.safety.operation_backup_rollback import (
    backup_to_recycle_bin,
)
from app.safety.operation_backup_rollback import (
    rollback_operation, rollback_session,
)
from app.safety.operation_maintenance import (
    cleanup_expired_backups,
)
# 2026-10-15 小欧 - 文档[35] 3.1.1 第五节: 补新模块导出。
#   路径检查九个模块此前一律走显式模块路径(from app.safety.path_check_entry import ...)未在包级导出;
#   现按文档要求补齐, 便于外部统一从 app.safety 取用。
from app.safety.path_check_entry import validate_tool_path
from app.safety.path_guard import (
    SYSTEM_PROTECTED_DIR_NAMES,
    is_code_root_path,
    is_disk_root,
    is_protected_root_itself,
    is_system_protected_path,
)
from app.safety.path_env import (
    get_default_allowed_paths,
    get_system_drive,
)
from app.safety.path_check_common import (
    check_preconditions,
    check_whitelist,
    resolve_allowed_paths,
)
from app.safety.read_path_check import validate_read as validate_path_for_read
from app.safety.write_path_check import validate_write as validate_path_for_write
from app.safety.delete_path_check import validate_delete as validate_path_for_delete
from app.safety.multi_path_check import (
    MULTI_ACTION_PARAMS,
    resolve_path_param,
    validate_multi_path,
)
from app.safety.shell_path_check import validate_shell
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
    # 路径检查三线分离(文档[35])
    "validate_tool_path",
    "validate_path_for_read", "validate_path_for_write", "validate_path_for_delete",
    "is_system_protected_path", "is_disk_root", "is_code_root_path",
    "is_protected_root_itself", "SYSTEM_PROTECTED_DIR_NAMES",
    "get_default_allowed_paths", "get_system_drive",
    "check_preconditions", "check_whitelist", "resolve_allowed_paths",
    "MULTI_ACTION_PARAMS", "validate_multi_path", "validate_shell",
]