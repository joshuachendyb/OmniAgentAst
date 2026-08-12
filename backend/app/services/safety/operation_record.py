
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - execute_with_safety返回值(bool)改(bool, Optional[str]): 原仅返bool, 操作失败吞掉真实错误(如"目标路径已存在...请设置overwrite=True"), 上层只能给LLM笼统"移动/复制/删除失败", LLM无法自我纠正。改后透传真实细节, LLM可据细节重试(如带overwrite=True)。
# 2026-07-18 - 小欧 - executed_at/backup_expires_at 改 get_utc_timestamp/convert_to_utc 入库 UTC Z; duration 计算 created_at_dt 兼容老/新数据
# 2026-07-18 - 小欧 - #1 fix: MODIFY 操作也生成备份(MODIFY回滚需原文件恢复), 用 op_type in (DELETE, MODIFY) 替代仅 DELETE, 扩展且不破原有DELETE路径
# 2026-07-25 - 小欧 - #2 fix: db.get_conn→get_conn_with_retry + 拆三段式(DB/文件/DB)消除长事务持锁, 彻底解决并行delete database is locked
# 2026-07-26 - 小欧 - 第二阶段注释加"先备份/再执行"子步骤说明(欧阳报告问题1修复)
# 2026-07-26 - 小沈 - execute_with_safety三段try拆分: Phase 1/3 DB异常logger.error; Phase 2工具异常只透传不log(透明原则+SRP)
# 2026-07-26 - 小沈 - operation_executor→operation_record改名, 名实对齐(主力职责为记录而非执行)
# 2026-07-26 - 小沈 - 合并 operation_recorder 三函数(record_operation/collect_file_info/update_op_failed)入此文件; backup_to_recycle_bin迁至operation_backup, 彻底理顺职责
# 2026-08-08 - 小欧 - 全程统一本地时区: 5处写入 get_utc_timestamp/convert_to_utc→get_local_iso_timestamp; duration修复: created_at_dt 先 astimezone() 转本地再去tzinfo, executed_at_dt 改 datetime.now() (naive本地), 两端类型一致
# 2026-08-11 - 小欧 - 备份失败仅warning留痕不阻断(北京老陈驱动): 备份尽量成功(backup_to_recycle_bin长路径支持), 万一仍失败只提示不终止删除/修改
#   (历史事故WinError206超长→部分备份→仍删除, 已由长路径支持+copy防自嵌套从源头缓解)
# 2026-08-11 - 小欧 - 三堂会审: 长路径触发条件修复。source_path.exists()/backup_path.exists()对超长路径(>260)返回False,
#   →超长源路径删除时备份被静默跳过(连warning都不触发, 复现"无备份删除"历史事故); 改os.path.exists(to_win_long_path(...))
# 2026-08-12 - 小欧 - A2-内部环(方案4.2.3步骤1): FileSafetyConfig 整体复制迁至 models.py(逻辑一字不改),
#   backup_to_recycle_bin 导入上移顶部; 本文件只保留记录职责(record/collect/update/execute_with_safety)
"""
operation_record — 操作记录和DB状态管理

职责: 记录文件操作到DB、更新状态、文件信息收集
小欧 2026-06-18 从operation_commands.py拆分，遵守SRP
"""
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from app.db import db
from app.db.models.operation_models import OperationType, OperationStatus
from app.logger import logger
from app.utils.id_utils import generate_operation_id
from app.utils.path_utils import to_win_long_path
from app.utils.time_utils import get_local_iso_timestamp, to_local_iso  # 小欧 2026-08-08 全程统一本地时区
from app.services.safety.hash_helper import compute_file_hash
from app.services.safety.models import FileSafetyConfig  # 小欧 2026-08-12 A2-内部环: 配置数据类独立
from app.services.safety.operation_backup import backup_to_recycle_bin


def collect_file_info(path: Path) -> Dict[str, Any]:
    """收集文件信息（长路径兼容: 普通Path.exists/stat对超长路径失效, 走\\?\前缀）"""
    if not path:
        return {"size": None, "hash": None, "extension": None, "is_directory": False}
    long_path = to_win_long_path(path)
    if not os.path.exists(long_path):
        return {"size": None, "hash": None, "extension": None, "is_directory": False}
    info = {"size": os.stat(long_path).st_size, "is_directory": os.path.isdir(long_path)}
    if os.path.isfile(long_path):
        info["hash"] = compute_file_hash(long_path)
        info["extension"] = Path(long_path).suffix.lower() if Path(long_path).suffix else None
    else:
        info["hash"] = None
        info["extension"] = None
    return info


def update_op_failed(cursor: sqlite3.Cursor, operation_id: str, error_message: str):
    """更新操作为失败状态"""
    cursor.execute(
        'UPDATE file_operations SET status = ?, error_message = ? WHERE operation_id = ?',
        (OperationStatus.FAILED.value, error_message, operation_id),
    )


def record_operation(
    task_id: str,
    operation_type: Optional[str] = None,
    source_path: Optional[Path] = None,
    destination_path: Optional[Path] = None,
    sequence_number: int = 0,
    file_size: Optional[int] = None,
    operation_id: Optional[str] = None,  # 小欧 2026-07-16 支持外部传入operation_id(贯通双表)
) -> Optional[str]:
    """记录文件操作到数据库（失败时返回None，不阻塞主流程）— 小健 2026-06-24 容错处理 — 小欧 2026-06-27 修复operation_type str/Enum不一致"""
    operation_id = operation_id or generate_operation_id()  # 小欧 2026-07-16 替代 f"op-{uuid4().hex}"
    space_impact_bytes = None
    try:
        if file_size is not None and operation_type is not None:
            if isinstance(operation_type, str):
                op_enum = OperationType(operation_type)
            else:
                op_enum = operation_type
            if op_enum == OperationType.CREATE:
                space_impact_bytes = -file_size
            elif op_enum == OperationType.DELETE:
                space_impact_bytes = file_size
        with db.get_conn_with_retry("operations") as conn:
            cursor = conn.cursor()
            op_type_str = operation_type.value if isinstance(operation_type, OperationType) else operation_type
            cursor.execute(
                '''INSERT INTO file_operations
                (operation_id, task_id, operation_type, status, source_path,
                 destination_path, sequence_number, file_size, space_impact_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (operation_id, task_id, op_type_str,
                  OperationStatus.PENDING.value,
                  str(source_path) if source_path else None,
                  str(destination_path) if destination_path else None,
                  sequence_number, file_size, space_impact_bytes, get_local_iso_timestamp()),
            )
        logger.debug(f"Operation recorded: {operation_id} - {op_type_str}")
        return operation_id
    except Exception as e:
        logger.warning(f"Failed to record operation: {e}, continue without recording")
        return None


def execute_with_safety(operation_id: str, operation_func, *args, **kwargs) -> Tuple[bool, Optional[str]]:
    """安全执行文件操作（自动备份、记录结果）

    【透明原则】— 小沈 2026-07-26
    operation_func的成败对此函数完全透明。本函数忠实记录operation_func的返回值，
    不判断、不篡改、不吞掉成功/失败状态。operation_func须遵守以下规则：
      - 预期失败：return False 或 (False, str)，不得 raise
      - 意外异常：让异常自然抛出，本函数catch后 return (False, str(e))
      - 成功：return True 或 (True, None)
    见 move_file.py:_move_sync(范式对齐参考) compress_files.py:executor传真实状态(如实记录参考)

    返回 (是否成功, 错误详情)：错误详情透传给上层，避免真因在链路中被吞掉 — 小欧 2026-07-15
    """
    config = FileSafetyConfig()

    # ===================== Phase 1: DB 操作（读取+标记EXECUTING）=====================
    # 基础设施异常 → logger.error，与工具业务无关 — 小沈 2026-07-26
    try:
        with db.get_conn_with_retry("operations") as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT operation_type, source_path, destination_path, created_at FROM file_operations WHERE operation_id = ?',
                (operation_id,),
            )
            row = cursor.fetchone()
            if not row:
                logger.error(f"Operation not found: {operation_id}")
                return False, None

            op_type, src_str, dst_str, created_at_str = row
            source_path = Path(src_str) if src_str else None
            dest_path = Path(dst_str) if dst_str else None
            created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) if isinstance(created_at_str, str) else created_at_str
            # 小欧 2026-08-08 v1.4修正: aware(迁移前UTC Z/+08:00旧数据)先 astimezone() 转本地再去tzinfo, 与 executed_at_dt(naive本地) 类型一致; naive(迁移后本地)保持不动
            if created_at_dt.tzinfo is not None:
                created_at_dt = created_at_dt.astimezone().replace(tzinfo=None)

            cursor.execute(
                'UPDATE file_operations SET status = ?, executed_at = ? WHERE operation_id = ?',
                (OperationStatus.EXECUTING.value, get_local_iso_timestamp(), operation_id),
            )
        # conn已提交+关闭，不持有数据库锁
    except Exception as e:
        logger.error(f"[Executor] Phase 1 DB error: {e}")
        return False, str(e)

    # ================ 备份：DELETE/MODIFY 操作前备份原文件到回收站 ====================
    backup_path = None
    # 2026-08-11 小欧 三堂会审: source_path.exists()对超长路径(>260)返回False→备份被静默跳过(复现"无备份删除"历史事故), 改长路径判断
    if source_path and os.path.exists(to_win_long_path(source_path)) and op_type in (
        OperationType.DELETE.value,
        OperationType.MODIFY.value,
    ):
        backup_path = backup_to_recycle_bin(source_path)
        # 2026-08-11 小欧 备份失败仅warning留痕不阻断(北京老陈驱动): 备份尽量成功(长路径支持),
        #   万一仍失败只提示, 不终止用户明确要求的删除/修改操作; 历史事故(WinError206超长)已由备份长路径支持缓解
        if backup_path is None:
            logger.warning(f"[Executor] 备份到回收站失败,继续执行(数据无回收站保护): op={operation_id}, source={source_path}")

    # ============= Phase 2: 工具执行（不 logger.error，只透传异常） ===================
    # 工具预期失败必须 return 而非 raise，真·意外异常（磁盘满/权限突变）才抛至此。
    # 此处只透传，不 logger.error — 小沈 2026-07-26
    try:
        success_raw = operation_func(*args, **kwargs)
    except Exception as e:
        return False, str(e)

    success = success_raw[0] if isinstance(success_raw, tuple) else bool(success_raw)
    error_detail = success_raw[1] if isinstance(success_raw, tuple) and len(success_raw) > 1 else None

    # ===================== Phase 3: 更新操作结果（短事务，带重试）=====================
    # 基础设施异常 → logger.error — 小沈 2026-07-26
    try:
        with db.get_conn_with_retry("operations") as conn:
            cursor = conn.cursor()
            if success:
                if op_type == OperationType.DELETE.value and backup_path and os.path.exists(to_win_long_path(backup_path)):
                    info = collect_file_info(backup_path)
                else:
                    # 2026-08-11 小欧 三堂会审: 目标/源exists()长路径兼容(超长路径普通Path.exists()为False)
                    target = dest_path if dest_path and os.path.exists(to_win_long_path(dest_path)) else source_path if source_path and os.path.exists(to_win_long_path(source_path)) else None
                    info = collect_file_info(target) if target else {}
                executed_at = get_local_iso_timestamp()
                executed_at_dt = datetime.now()  # 小欧 2026-08-08 全程统一本地时区: naive本地, 与 created_at_dt(转本地naive) 类型一致
                duration_ms = int((executed_at_dt - created_at_dt).total_seconds() * 1000) if created_at_dt else None
                space_impact = 0
                if op_type == OperationType.DELETE.value and info.get("size"):
                    space_impact = info["size"]
                elif op_type == OperationType.CREATE.value and info.get("size"):
                    space_impact = -info["size"]
                cursor.execute(
                    '''UPDATE file_operations SET status = ?, backup_path = ?, backup_expires_at = ?,
                        file_size = ?, file_hash = ?, is_directory = ?,
                        file_extension = ?, duration_ms = ?, space_impact_bytes = ?, executed_at = ?
                    WHERE operation_id = ?''',
                    (OperationStatus.SUCCESS.value,
                     str(backup_path) if backup_path else None,
                     to_local_iso(datetime.now() + timedelta(days=config.BACKUP_RETENTION_DAYS)) if backup_path else None,
                     info.get("size"), info.get("hash"), info.get("is_directory", False),
                     info.get("extension"), duration_ms, space_impact, get_local_iso_timestamp(), operation_id),
                )
                logger.debug(f"Operation executed successfully: {operation_id}")
                return True, None
            else:
                update_op_failed(cursor, operation_id, error_detail or "Operation failed")
                return False, error_detail
    except Exception as e:
        logger.error(f"[Executor] Phase 3 DB error: {e}")
        return False, str(e)

