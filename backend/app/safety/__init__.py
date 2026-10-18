# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-10 - 小欧 - 拍平 file_safety/ 目录到 safety/
# 2026-07-26 - 小沈 - import 路径对应 operation_record/operation_backup 改名+职责理顺
# 2026-08-12 - 小欧 - A2-内部环(方案4.2.3): FileSafetyConfig 导入改 models, cleanup_expired_backups 导入改 operation_maintenance
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件全部 import 由 app.services.safety.xxx 改 app.safety.xxx(配合 tools 禁 app.services 守护规则)
# 2026-10-17 北京老陈裁定 - check_preconditions 迁至 app.utils.path_utils, 本文件取消该符号的 import 与 __all__ 转出(禁 backward 再导出)
# 2026-10-17 - 小欧 - 路径检查口正名(S8): validate_tool_path→check_tool_path_permission、validate_dual_path→check_dual_permission、validate_shell→check_shell_permission; import 与 __all__ 同步, 旧名退场(禁留转发层)。
# 2026-10-17 - 小欧 - 补导出三线封装口 check_read/write/delete_permission(此前仅导出三线原始 validate_*, 与 check_dual/shell_permission 契约不对称)。
# 2026-10-17 - 小欧 - DUAL_ACTION_PARAMS 表体上移 tool_constants, 此处删其 import 与 __all__(无外部消费方)。
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
# 2026-10-15 小欧 - 补新模块导出。
#   路径检查九个模块此前一律走显式模块路径(from app.safety.path_legality_router import ...)未在包级导出;
#   现按文档要求补齐, 便于外部统一从 app.safety 取用。
# 2026-10-16 小欧 - tool去检查化: 删 validate_path_for_write/delete 别名导出(与工具层 for_* 同名不同义,
#   实测全仓零外部使用); 改直挂 validate_read/write/delete 真名。
from app.safety.path_legality_router import check_tool_path_permission
from app.safety.path_classify_category import (
    SYSTEM_PROTECTED_DIR_NAMES,
    is_code_root_path,
    is_disk_root,
    is_allowed_root_itself,
    is_system_protected_path,
)
from app.safety.path_env import (
    get_default_allowed_paths,
    get_system_drive,
)
from app.safety.path_check_common import (
    check_whitelist,
    resolve_allowed_paths,
)
# 2026-10-17 北京老陈裁定: check_preconditions 已迁 app.utils.path_utils, 此处不再转出(禁 backward 再导出)
from app.safety.read_path_check import validate_read, check_read_permission
from app.safety.write_path_check import validate_write, check_write_permission
from app.safety.delete_path_check import validate_delete, check_delete_permission
from app.safety.dual_path_check import (
    check_dual_permission,
)
# 2026-10-17 小欧 - DUAL_ACTION_PARAMS 表体已上移 tool_constants(与 DUAL_PATH_TOOLS 同层),
#   本层不再转出(无外部消费方, 禁 backward 再导出); 消费方一律 from app.tools.tool_constants import。
# 2026-10-16 小欧 - 三堂会审删死导入(YAGNI): resolve_path_param 原在此 import 但不在 __all__,
#   故 `from app.safety import *` 从来拿不到它; 实测全仓 3 处消费方一律走
#   `dual_path_check.resolve_path_param` 模块限定调用, 无一处用顶层路径 —— 纯死导入, 删。
from app.safety.shell_path_check import check_shell_permission
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
    # 路径检查三线分离
    "check_tool_path_permission",
    "validate_read", "validate_write", "validate_delete",  # 2026-10-16 小欧 - 删名实不符别名(与工具层 for_* 同名不同义)
    "check_read_permission", "check_write_permission", "check_delete_permission",  # 2026-10-17 小欧 - 三线封装口补齐(与 check_dual/shell_permission 对称)
    "is_system_protected_path", "is_disk_root", "is_code_root_path",
    "is_allowed_root_itself", "SYSTEM_PROTECTED_DIR_NAMES",
    "get_default_allowed_paths", "get_system_drive",
    "check_whitelist", "resolve_allowed_paths",
    "check_dual_permission", "check_shell_permission",
]